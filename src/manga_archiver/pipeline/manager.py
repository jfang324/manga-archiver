from __future__ import annotations

import asyncio
import logging
import tracemalloc
from asyncio import Queue
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_PROVIDER_RATE_LIMIT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_RESOLVE_WORKERS,
    DEFAULT_UPLOAD_WORKERS,
)
from ..integrations.content_providers import ContentProviderManager
from ..integrations.storage_providers.google_drive import GoogleDriveFolderCache
from ..models.app_config import AppConfig
from ..utils import DownloadClient
from ..workers.jobs import (
    FetchingResourcesJob,
    Job,
    NotificationJob,
)
from ..workers.scheduler import RateLimitAwareScheduler, SchedulerConfig, SchedulerFeedback
from ..workers.types import JobMetadata, JobStatus
from .benchmark import BenchmarkReport, format_benchmark_results
from .job_registry import PipelineJobRegistry
from .worker_manager import WorkerManager

if TYPE_CHECKING:
    from ..persistence.google_drive_token_store import GoogleApiStoredToken

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable data container for the configuration of a pipeline.

    Attributes:
        num_resolve_workers (int): The number of resolve workers to use
        num_download_workers (int): The number of download workers to use
        num_merge_workers (int): The number of merge workers to use
        num_upload_workers (int): The number of upload workers to use
        resolve_rate_limit (int): Per-provider rate limit for resolve operations
        download_rate_limit (int): Per-provider rate limit for download operations
        resolve_queue_size (int): Size of the resolve queue
        download_queue_size (int): Size of the download queue
        merge_queue_size (int): Size of the merge queue
        upload_queue_size (int): Size of the upload queue
        resolve_scheduler_enabled (bool): Whether to schedule resolve jobs before workers
        resolve_scheduler_config (SchedulerConfig): Configuration for resolve job scheduling
        benchmark_enabled (bool): Whether to enable benchmark metrics collection
    """

    num_resolve_workers: int = DEFAULT_RESOLVE_WORKERS
    num_download_workers: int = DEFAULT_DOWNLOAD_WORKERS
    num_merge_workers: int = DEFAULT_MERGE_WORKERS
    num_upload_workers: int = DEFAULT_UPLOAD_WORKERS

    resolve_rate_limit: int = DEFAULT_PROVIDER_RATE_LIMIT
    download_rate_limit: int = DEFAULT_DOWNLOAD_RATE_LIMIT

    resolve_queue_size: int = DEFAULT_QUEUE_SIZE
    download_queue_size: int = (
        DEFAULT_QUEUE_SIZE * 2
    )  # download jobs are small and don't need much back-pressure; it's better to optimize rate limit usage
    merge_queue_size: int = DEFAULT_QUEUE_SIZE
    upload_queue_size: int = DEFAULT_QUEUE_SIZE

    resolve_scheduler_enabled: bool = True
    resolve_scheduler_config: SchedulerConfig = field(default_factory=SchedulerConfig)

    benchmark_enabled: bool = False


@dataclass(frozen=True)
class EnqueueJobsResult:
    """Summary of jobs accepted into or skipped before the pipeline."""

    accepted_count: int = 0
    skipped_count: int = 0


class PipelineManager:
    """Controls the multi-stage processing pipeline, managing workers, queues, and job lifecycle.

    Orchestrates the flow of jobs through fetch → download → merge → upload stages,
    with built-in rate limiting, error handling, and status tracking.
    """

    def __init__(
        self,
        provider_manager: ContentProviderManager,
        download_client: DownloadClient,
        config: PipelineConfig,
        google_drive_token: GoogleApiStoredToken | None = None,
        google_drive_folder_cache: GoogleDriveFolderCache | None = None,
    ) -> None:
        """Initialize the pipeline manager.

        Args:
            provider_manager: The content provider manager
            download_client: The client for downloading images
            config: The configuration for the pipeline
            google_drive_token: Token for creating Google Drive upload clients
            google_drive_folder_cache: Shared Google Drive folder cache
        """
        self._resolve_queue: Queue[Job] = Queue(
            maxsize=config.resolve_queue_size if config.resolve_scheduler_enabled else 0
        )
        self._download_queue: Queue[Job] = Queue(maxsize=(config.download_queue_size))
        self._merge_queue: Queue[Job] = Queue(maxsize=config.merge_queue_size)
        self._upload_queue: Queue[Job] = Queue(maxsize=config.upload_queue_size)
        self._notification_queue: Queue[NotificationJob] = Queue()

        self._pipeline_entry_queue: Queue[Job] = self._resolve_queue

        self._resolve_scheduler: RateLimitAwareScheduler | None = None
        self._resolve_scheduler_input_queue: Queue[Job] = Queue()
        self._resolve_scheduler_feedback_queue: Queue[SchedulerFeedback] | None = None

        if config.resolve_scheduler_enabled:
            self._pipeline_entry_queue = self._resolve_scheduler_input_queue
            self._resolve_scheduler_feedback_queue = Queue()

            self._resolve_scheduler = RateLimitAwareScheduler(
                input_queue=self._resolve_scheduler_input_queue,
                output_queue=self._resolve_queue,
                feedback_queue=self._resolve_scheduler_feedback_queue,
                config=config.resolve_scheduler_config,
            )

        self._job_registry = PipelineJobRegistry()

        self._worker_manager = WorkerManager(
            resolve_queue=self._resolve_queue,
            download_queue=self._download_queue,
            merge_queue=self._merge_queue,
            upload_queue=self._upload_queue,
            notification_queue=self._notification_queue,
            num_resolve_workers=config.num_resolve_workers,
            num_download_workers=config.num_download_workers,
            num_merge_workers=config.num_merge_workers,
            num_upload_workers=config.num_upload_workers,
            benchmark_enabled=config.benchmark_enabled,
            provider_manager=provider_manager,
            download_client=download_client,
            google_drive_token=google_drive_token,
            google_drive_folder_cache=google_drive_folder_cache,
            on_status_update=self._job_registry.record_status_update,
            resolve_scheduler_feedback_queue=self._resolve_scheduler_feedback_queue,
        )

        self._benchmark_enabled = config.benchmark_enabled

    def get_jobs(self) -> dict[str, tuple[JobStatus, JobMetadata]]:
        """Return a copy of the current job statuses."""
        return self._job_registry.get_jobs()

    def get_incomplete_jobs(self) -> list[FetchingResourcesJob]:
        """Return a list of all incomplete jobs as FetchingResourcesJob instances."""
        return self._job_registry.get_incomplete_jobs()

    async def retry_failed_jobs(self) -> int:
        """Re-queue all failed jobs for retry through the scheduler.

        Returns:
            int: Number of jobs re-queued
        """
        jobs = self._job_registry.pop_failed_jobs()
        if not jobs:
            return 0

        await self.enqueue_jobs(jobs)

        return len(jobs)

    def _validate_job(self, job: FetchingResourcesJob) -> None:
        """Validate job has all required fields and valid values.

        Args:
            job: The job to validate

        Raises:
            ValueError: If any required field is missing or invalid
        """
        if not job.id:
            raise ValueError("Job is missing id")
        if not job.manga_title:
            raise ValueError(f"Job {job.id} is missing manga_title")
        if not job.chapter_title:
            raise ValueError(f"Job {job.id} is missing chapter_title")

        if not isinstance(job.chapter_number, float):
            raise ValueError(
                f"Job {job.id} chapter_number '{job.chapter_number}' must be float type"
            )

        if not job.chapter_id:
            raise ValueError(f"Job {job.id} is missing chapter_id")

        if not isinstance(job.app_config, AppConfig):
            raise ValueError(f"Job {job.id} app_config must be AppConfig instance")

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]) -> EnqueueJobsResult:
        accepted_count = 0
        skipped_count = 0
        seen_ids: set[str] = set()

        # Sequential to maintain ordering; parallel would save negligible time
        for job in jobs:
            try:
                self._validate_job(job)
            except ValueError as e:
                logger.error("Skipping invalid job: %s", e)
                skipped_count += 1
                continue

            if job.chapter_id in seen_ids:
                logger.error("Skipping duplicate job id: %s", job.chapter_id)
                skipped_count += 1
                continue

            notification_job = NotificationJob(
                id=job.chapter_id,
                status=JobStatus.QUEUED,
                metadata=job.to_metadata(),
            )

            await asyncio.gather(
                *[
                    self._notification_queue.put(notification_job),
                    self._pipeline_entry_queue.put(job),
                ]
            )
            seen_ids.add(job.chapter_id)
            accepted_count += 1

        return EnqueueJobsResult(accepted_count=accepted_count, skipped_count=skipped_count)

    async def start(self, jobs: list[FetchingResourcesJob] | None = None) -> None:
        """Start all workers in the pipeline.

        Args:
            jobs | None: Optional list of jobs to enqueue BEFORE workers start.
                  This ensures workers have work ready immediately.
        """
        # Enqueue jobs BEFORE starting workers
        if jobs:
            await self.enqueue_jobs(jobs)

        if self._benchmark_enabled:
            tracemalloc.start()

        runnables = [self._worker_manager.start()]

        if self._resolve_scheduler is not None:
            runnables.append(self._resolve_scheduler.run())

        await asyncio.gather(*runnables)

    def stop(self) -> None:
        """Stop all workers in the pipeline.

        Signals all workers to stop processing.
        """
        if self._resolve_scheduler is not None:
            self._resolve_scheduler.stop()

        self._worker_manager.stop()

    def get_benchmark_results(self) -> BenchmarkReport | None:
        """Get benchmark results if benchmarking is enabled.

        Returns:
            BenchmarkReport | None: Benchmark metrics, or None if benchmarking is not enabled
        """
        if not self._benchmark_enabled:
            return None

        benchmark = self._worker_manager.notification_worker._benchmark
        if benchmark is None:
            return None

        return format_benchmark_results(benchmark.get_aggregates())
