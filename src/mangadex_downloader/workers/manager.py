import asyncio
import logging
import time
import tracemalloc
from asyncio import Queue, Semaphore
from collections import deque
from dataclasses import dataclass
from typing import Callable

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_JOB_EXPIRY_SECONDS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_RESOLVE_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
    DEFAULT_UPLOAD_WORKERS,
)
from ..enums import JobStatus
from ..integrations.content_providers import MangaDexApiClient
from ..integrations.storage_providers.google_drive import GoogleDriveClient
from ..utils import DownloadClient, MultiFormatExporter
from .base import WorkerConfig
from .download_worker import DownloadWorker
from .jobs import (
    FetchingResourcesJob,
    Job,
    JobMetadata,
    NotificationJob,
)
from .merge_worker import MergeWorker
from .notification_worker import NotificationWorker
from .resolve_worker import ResolveWorker
from .upload_worker import UploadWorker

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """A data container for the configuration of a pipeline.

    Attributes:
        num_resolve_workers: The number of resolve workers to use
        num_download_workers: The number of download workers to use
        num_merge_workers: The number of merge workers to use
        num_upload_workers: The number of upload workers to use
        resolve_rate_limit: The global rate limit for resolve workers (requests per second)
        download_rate_limit: The global rate limit for download workers (requests per second)
    """

    num_resolve_workers: int = DEFAULT_RESOLVE_WORKERS
    num_download_workers: int = DEFAULT_DOWNLOAD_WORKERS
    num_merge_workers: int = DEFAULT_MERGE_WORKERS
    num_upload_workers: int = DEFAULT_UPLOAD_WORKERS

    resolve_rate_limit: int = DEFAULT_RESOLVE_RATE_LIMIT
    download_rate_limit: int = DEFAULT_DOWNLOAD_RATE_LIMIT


class PipelineManager:
    """A class that controls the processing pipeline, managing and configuring workers and queues.

    Attributes:
        mangadex_api_client: The API client for MangaDex
        download_client: The client for downloading images
        config: The configuration for the pipeline
        google_drive_client: The Google Drive client for uploads (optional)
    """

    def __init__(
        self,
        mangadex_api_client: MangaDexApiClient,
        download_client: DownloadClient,
        config: PipelineConfig,
        google_drive_client: GoogleDriveClient | None = None,
        benchmark_callback: Callable[[float, float], None] | None = None,
    ):
        """Initialize the pipeline manager.

        Args:
            mangadex_api_client: The API client for MangaDex
            download_client: The client for downloading images
            config: The configuration for the pipeline
            benchmark_callback: Optional callback for benchmark results
        """
        self._resolve_queue: Queue[Job] = Queue()
        self._download_queue: Queue[Job] = Queue()
        self._merge_queue: Queue[Job] = Queue()
        self._upload_queue: Queue[Job] = Queue()
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

        self._track_memory = False
        self._benchmark_callback = benchmark_callback

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
        )

    def _on_status_update(
        self, job_id: str, status: JobStatus, metadata: JobMetadata
    ) -> None:
        """
        Callback to update job status in the internal dict with automatic expiry.
        Modification of state MUST be done here to avoid race conditions.
        """
        self._job_statuses[job_id] = (status, metadata)

        # Only add to expiry queue if terminal state
        if status in (JobStatus.COMPLETED, JobStatus.FAILED):
            self._job_expiry_queue.append((time.time(), job_id))

        # Check oldest entries - O(1) amortized
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
            1
            for status, _ in self._job_statuses.values()
            if status not in (JobStatus.COMPLETED, JobStatus.FAILED)
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
                start_time=-1,
                end_time=-1,
                status=JobStatus.QUEUED,
            )

            await asyncio.gather(
                *[
                    self._notification_queue.put(notification_job),
                    self._resolve_queue.put(job),
                ]
            )

    def _wrap_benchmark_callback(
        self, original_callback: Callable[[float, float], None] | None
    ) -> Callable[[float, float], None]:
        """Wrap benchmark callback to include memory logging."""

        def wrapped_callback(earliest_start: float, latest_end: float) -> None:
            if self._track_memory:
                _, peak = tracemalloc.get_traced_memory()
                peak_mb = peak / 1024 / 1024
                logger.debug(
                    "Benchmark: time=%.2fms, peak_memory=%.2fMB",
                    (latest_end - earliest_start) / 1_000_000,
                    peak_mb,
                )

            if original_callback:
                original_callback(earliest_start, latest_end)

        return wrapped_callback

    async def start(self):
        """Start all workers in the pipeline.

        Launches all worker pools (resolve, download, merge, upload, notification)
        and blocks until all workers complete.
        """
        if self._track_memory:
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
