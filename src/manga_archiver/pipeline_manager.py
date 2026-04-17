import asyncio
import logging
import time
import tracemalloc
from asyncio import Queue, Semaphore
from collections import deque
from dataclasses import dataclass

from .constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_JOB_EXPIRY_SECONDS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_RESOLVE_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
    DEFAULT_UPLOAD_WORKERS,
)
from .enums import JobStatus
from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .models.output_format import OutputFormat
from .utils import DownloadClient
from .workers import (
    FetchingResourcesJob,
    Job,
    JobMetadata,
    NotificationJob,
    WorkerManager,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PipelineConfig:
    """Immutable data container for the configuration of a pipeline.

    Attributes:
        num_resolve_workers (int): The number of resolve workers to use
        num_download_workers (int): The number of download workers to use
        num_merge_workers (int): The number of merge workers to use
        num_upload_workers (int): The number of upload workers to use
        resolve_rate_limit (int): The global rate limit for resolve workers (requests per second)
        download_rate_limit (int): The global rate limit for download workers (requests per second)
        benchmark_enabled (bool): Whether to enable benchmark metrics collection
    """

    num_resolve_workers: int = DEFAULT_RESOLVE_WORKERS
    num_download_workers: int = DEFAULT_DOWNLOAD_WORKERS
    num_merge_workers: int = DEFAULT_MERGE_WORKERS
    num_upload_workers: int = DEFAULT_UPLOAD_WORKERS

    resolve_rate_limit: int = DEFAULT_RESOLVE_RATE_LIMIT
    download_rate_limit: int = DEFAULT_DOWNLOAD_RATE_LIMIT

    download_queue_size: int = DEFAULT_QUEUE_SIZE
    merge_queue_size: int = DEFAULT_QUEUE_SIZE
    upload_queue_size: int = DEFAULT_QUEUE_SIZE

    benchmark_enabled: bool = False


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
        google_drive_client: GoogleDriveClient | None = None,
    ) -> None:
        """Initialize the pipeline manager.

        Args:
            provider_manager: The content provider manager
            download_client: The client for downloading images
            config: The configuration for the pipeline
            google_drive_client: The Google Drive client for uploading
        """
        self._resolve_queue: Queue[Job] = Queue()
        self._download_queue: Queue[Job] = Queue(maxsize=config.download_queue_size)
        self._merge_queue: Queue[Job] = Queue(maxsize=config.merge_queue_size)
        self._upload_queue: Queue[Job] = Queue(maxsize=config.upload_queue_size)
        self._notification_queue: Queue[NotificationJob] = Queue()

        self._job_statuses: dict[str, tuple[JobStatus, JobMetadata]] = {}
        self._job_expiry_queue: deque[tuple[float, str]] = deque()
        self._job_expiry_seconds: int = DEFAULT_JOB_EXPIRY_SECONDS

        self._resolve_semaphore: Semaphore = Semaphore(config.resolve_rate_limit)
        self._download_semaphore: Semaphore = Semaphore(config.download_rate_limit)

        self._worker_manager = WorkerManager(
            resolve_queue=self._resolve_queue,
            download_queue=self._download_queue,
            merge_queue=self._merge_queue,
            upload_queue=self._upload_queue,
            notification_queue=self._notification_queue,
            resolve_semaphore=self._resolve_semaphore,
            download_semaphore=self._download_semaphore,
            num_resolve_workers=config.num_resolve_workers,
            num_download_workers=config.num_download_workers,
            num_merge_workers=config.num_merge_workers,
            num_upload_workers=config.num_upload_workers,
            benchmark_enabled=config.benchmark_enabled,
            provider_manager=provider_manager,
            download_client=download_client,
            google_drive_client=google_drive_client,
            on_status_update=self._on_status_update,
        )

        self._benchmark_enabled = config.benchmark_enabled

    def is_done(self) -> bool:
        """Return whether all jobs are in a terminal state."""
        all_jobs = self._job_statuses.values()

        return all(status in (JobStatus.COMPLETED, JobStatus.FAILED) for status, _ in all_jobs)

    def _on_status_update(self, job_id: str, status: JobStatus, metadata: JobMetadata) -> None:
        """Update job status in internal dict with automatic expiry.

        Uses a queue to track completed jobs for efficient expiry checking.
        Modification of state MUST be done here to avoid race conditions.
        """
        self._job_statuses[job_id] = (status, metadata)

        # Add to expiry queue when job completes
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            self._job_expiry_queue.append((time.time(), job_id))

        # Check and remove expired jobs (O(1) amortized)
        while self._job_expiry_queue:
            oldest_timestamp, oldest_job_id = self._job_expiry_queue[0]
            if time.time() - oldest_timestamp > self._job_expiry_seconds:
                self._job_expiry_queue.popleft()
                self._job_statuses.pop(oldest_job_id, None)
            else:
                break

    def get_jobs(self) -> dict[str, tuple[JobStatus, JobMetadata]]:
        """Return a copy of the current job statuses."""
        return self._job_statuses.copy()

    def incomplete_job_count(self) -> int:
        """Return the number of jobs not in a terminal state."""
        return sum(
            [
                1
                for status, _ in self._job_statuses.values()
                if status not in (JobStatus.COMPLETED, JobStatus.FAILED)
            ]
        )

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

        if not isinstance(job.output_format, OutputFormat):
            raise ValueError(f"Job {job.id} output_format must be OutputFormat enum")

        if not job.output_directory or not job.output_directory.exists():
            raise ValueError(f"Job {job.id} output_directory does not exist")

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]):
        # Sequential to maintain ordering; parallel would save negligible time
        for job in jobs:
            try:
                self._validate_job(job)
            except ValueError as e:
                logger.error("Skipping invalid job: %s", e)
                continue

            notification_job = NotificationJob(
                id=job.chapter_id,
                manga_title=job.manga_title,
                chapter_number=job.chapter_number,
                chapter_title=job.chapter_title,
                output_directory=job.output_directory,
                output_format=job.output_format,
                status=JobStatus.QUEUED,
            )

            await asyncio.gather(
                *[
                    self._notification_queue.put(notification_job),
                    self._resolve_queue.put(job),
                ]
            )

    async def start(self, jobs: list[FetchingResourcesJob] | None = None):
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

        await self._worker_manager.start()

    def stop(self) -> None:
        """Stop all workers in the pipeline.

        Signals all workers to stop processing.
        """
        self._worker_manager.stop()

    def get_benchmark_results(self) -> dict | None:
        """Get benchmark results if benchmarking is enabled.

        Returns:
            Dictionary with benchmark metrics, or None if benchmarking is not enabled
        """
        if not self._benchmark_enabled:
            return None

        benchmark = self._worker_manager.notification_worker._benchmark
        if benchmark is None:
            return None

        aggregates = benchmark.get_aggregates()
        return {
            "total_job_count": aggregates.total_job_count,
            "fetching_total_ms": aggregates.total_time_per_phase.get(
                JobStatus.FETCHING_RESOURCES, 0
            )
            / 1_000_000,
            "fetching_avg_ms": aggregates.avg_time_per_phase.get(JobStatus.FETCHING_RESOURCES, 0)
            / 1_000_000,
            "downloading_total_ms": aggregates.total_time_per_phase.get(JobStatus.DOWNLOADING, 0)
            / 1_000_000,
            "downloading_avg_ms": aggregates.avg_time_per_phase.get(JobStatus.DOWNLOADING, 0)
            / 1_000_000,
            "merging_total_ms": aggregates.total_time_per_phase.get(JobStatus.MERGING, 0)
            / 1_000_000,
            "merging_avg_ms": aggregates.avg_time_per_phase.get(JobStatus.MERGING, 0) / 1_000_000,
            "uploading_total_ms": aggregates.total_time_per_phase.get(JobStatus.UPLOADING, 0)
            / 1_000_000,
            "uploading_avg_ms": aggregates.avg_time_per_phase.get(JobStatus.UPLOADING, 0)
            / 1_000_000,
            "avg_total_time_ms": aggregates.avg_total_time / 1_000_000,
            "peak_memory_mb": aggregates.peak_memory_mb,
            "highest_perceived_download_time_ms": aggregates.highest_perceived_download_time
            / 1_000_000,
            "highest_perceived_end_to_end_ms": aggregates.highest_perceived_end_to_end / 1_000_000,
        }
