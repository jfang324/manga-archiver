import asyncio
import logging
import time
from asyncio import Queue
from collections.abc import Callable

from .benchmark import BenchmarkManager
from .jobs import NotificationJob
from .types import JobMetadata, JobStatus

logger = logging.getLogger(__name__)


class NotificationWorker:
    """Worker that tracks job statuses and updates the PipelineManager's job status dict.

    Attributes:
        on_status_update (Callable[[str, JobStatus, JobMetadata], None]): Callback to update job status in PipelineManager
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue,
        on_status_update: Callable[[str, JobStatus, JobMetadata], None],
        benchmark: BenchmarkManager | None = None,
    ) -> None:
        """Initialize the notification worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The queue to receive notification jobs from
            on_status_update: Callback to update job status in PipelineManager
            benchmark: Optional benchmark manager for collecting metrics
        """
        self._id = worker_id
        self._input_queue = input_queue
        self._on_status_update = on_status_update
        self._benchmark = benchmark
        self._running = False

    async def run(self) -> None:
        """Pull notification jobs from the queue and process them continuously.

        Continuously pulls notification jobs from the queue and processes them.
        """
        self._running = True

        while self._running:
            try:
                job: NotificationJob = await self._input_queue.get()

                try:
                    await self._do_work(job)
                finally:
                    self._input_queue.task_done()
            except asyncio.CancelledError:  # noqa: PERF203 - required for graceful shutdown of async worker
                self._running = False
                break

    async def _do_work(self, job: NotificationJob) -> None:
        """Process a notification job and update the job status.

        Args:
            job: The notification job containing status update information
        """
        metadata = JobMetadata(
            chapter_id=job.id,
            manga_title=job.manga_title,
            chapter_number=job.chapter_number,
            chapter_title=job.chapter_title,
            app_config=job.app_config,
            source=job.source,
        )

        # Set completed_at for terminal statuses
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            metadata.completed_at = time.time()

        self._on_status_update(job.id, job.status, metadata)

        # Record benchmark timing
        if self._benchmark:
            self._benchmark.record(job.id, job.status, job.start_time, job.end_time)

        if self._benchmark and job.status == JobStatus.COMPLETED:
            aggregates = self._benchmark.get_aggregates()
            logger.info(
                "Benchmark [%s]: jobs=%d, fetch_avg_ms=%.2f, download_avg_ms=%.2f, "
                "merge_avg_ms=%.2f, upload_avg_ms=%.2f, peak_memory_mb=%.2f",
                job.id,
                aggregates.total_job_count,
                aggregates.avg_time_per_phase.get(JobStatus.FETCHING_RESOURCES, 0) / 1_000_000,
                aggregates.avg_time_per_phase.get(JobStatus.DOWNLOADING, 0) / 1_000_000,
                aggregates.avg_time_per_phase.get(JobStatus.MERGING, 0) / 1_000_000,
                aggregates.avg_time_per_phase.get(JobStatus.UPLOADING, 0) / 1_000_000,
                aggregates.peak_memory_mb,
            )

    def stop(self) -> None:
        """Stop the notification worker."""
        self._running = False
