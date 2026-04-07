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
from .integrations.content_providers import MangaDexApiClient
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .utils import DownloadClient, MultiFormatExporter
from .workers import (
    BenchmarkManager,
    DownloadWorker,
    FetchingResourcesJob,
    Job,
    JobMetadata,
    MergeWorker,
    NotificationJob,
    NotificationWorker,
    ResolveWorker,
    UploadWorker,
    WorkerConfig,
)

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """A data container for the configuration of a pipeline.

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
        mangadex_api_client: MangaDexApiClient,
        download_client: DownloadClient,
        config: PipelineConfig,
        google_drive_client: GoogleDriveClient | None = None,
    ) -> None:
        """Initialize the pipeline manager.

        Args:
            mangadex_api_client: The API client for MangaDex
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

        self._resolve_pool: list[ResolveWorker] = [
            ResolveWorker(
                id=f"resolve_worker_{index}",
                input_queue=self._resolve_queue,
                output_queue=self._download_queue,
                notification_queue=self._notification_queue,
                config=WorkerConfig(),
                api_client=mangadex_api_client,
                semaphore=self._resolve_semaphore,
            )
            for index in range(config.num_resolve_workers)
        ]
        self._download_pool: list[DownloadWorker] = [
            DownloadWorker(
                id=f"download_worker_{index}",
                input_queue=self._download_queue,
                output_queue=self._merge_queue,
                notification_queue=self._notification_queue,
                config=WorkerConfig(),
                download_client=download_client,
                semaphore=self._download_semaphore,
            )
            for index in range(config.num_download_workers)
        ]
        self._merge_pool: list[MergeWorker] = [
            MergeWorker(
                id=f"merge_worker_{index}",
                input_queue=self._merge_queue,
                output_queue=self._upload_queue if google_drive_client else None,
                notification_queue=self._notification_queue,
                config=WorkerConfig(),
                multi_format_exporter=MultiFormatExporter(),
            )
            for index in range(config.num_merge_workers)
        ]

        self._upload_pool: list[UploadWorker] = []

        if google_drive_client:
            self._upload_pool = [
                UploadWorker(
                    id=f"upload_worker_{index}",
                    input_queue=self._upload_queue,
                    output_queue=None,
                    notification_queue=self._notification_queue,
                    config=WorkerConfig(),
                    google_drive_client=google_drive_client,
                )
                for index in range(config.num_upload_workers)
            ]

        self._notification_worker = NotificationWorker(
            id="notification_worker",
            input_queue=self._notification_queue,
            on_status_update=self._on_status_update,
            benchmark=BenchmarkManager() if config.benchmark_enabled else None,
        )

        self._benchmark_enabled = config.benchmark_enabled

    def _on_status_update(self, job_id: str, status: JobStatus, metadata: JobMetadata) -> None:
        """Callback to update job status in the internal dict with automatic expiry.

        Uses a queue to track completed jobs for efficient expiry checking.
        Modification of state MUST be done here to avoid race conditions.
        """  # noqa: D401
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

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]):
        # Sequential to maintain ordering; parallel would save negligible time
        for job in jobs:
            notification_job = NotificationJob(
                id=job.chapter_id,
                manga_title=job.manga_title,
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

    async def start(self):
        """Start all workers in the pipeline.

        Launches all worker pools (resolve, download, merge, upload, notification)
        """
        if self._benchmark_enabled:
            tracemalloc.start()

        all_workers = (
            [self._notification_worker]
            + self._resolve_pool
            + self._download_pool
            + self._merge_pool
            + self._upload_pool
        )

        await asyncio.gather(*[w.run() for w in all_workers])

    def stop(self) -> None:
        """Stop all workers in the pipeline.

        Signals all workers to stop processing.
        """
        for worker in (
            [self._notification_worker]
            + self._resolve_pool
            + self._download_pool
            + self._merge_pool
            + self._upload_pool
        ):
            worker.stop()

    def get_benchmark_results(self) -> dict | None:
        """Get benchmark results if benchmarking is enabled.

        Returns:
            Dictionary with benchmark metrics, or None if benchmarking is not enabled
        """
        if not self._benchmark_enabled:
            return None

        benchmark = self._notification_worker._benchmark
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
