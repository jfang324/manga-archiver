import asyncio
import logging
import time
from asyncio import Queue
from typing import Callable

from ..enums import JobStatus
from .benchmark import BenchmarkManager, BenchmarkPhase
from .jobs import JobMetadata, NotificationJob

logger = logging.getLogger(__name__)

STATUS_TO_BENCHMARK = {
    JobStatus.FETCHING_RESOURCES: "fetching_resources",
    JobStatus.DOWNLOADING: "downloading",
    JobStatus.MERGING: "merging",
    JobStatus.UPLOADING: "uploading",
}


class NotificationWorker:
    """Worker that tracks job statuses and updates the PipelineManager's job status dict.

    Attributes:
        on_status_update (Callable[[str, JobStatus, JobMetadata], None]): Callback to update job status in PipelineManager
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue,
        on_status_update: Callable[[str, JobStatus, JobMetadata], None],
        benchmark: BenchmarkManager | None = None,
    ) -> None:
        """Initialize the notification worker.

        Args:
            id: The ID of the worker
            input_queue: The queue to receive notification jobs from
            on_status_update: Callback to update job status in PipelineManager
            benchmark: Optional benchmark manager for collecting metrics
        """
        self._id = id
        self._input_queue = input_queue
        self._on_status_update = on_status_update
        self._benchmark = benchmark
        self._running = False

    async def run(self) -> None:
        """Main loop for the notification worker.

        Continuously pulls notification jobs from the queue and processes them.
        """
        self._running = True

        while self._running:
            try:
                job: NotificationJob = await self._input_queue.get()
                await self._do_work(job)
                self._input_queue.task_done()
            except asyncio.CancelledError:
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
            chapter_title=job.chapter_title,
        )

        # Set completed_at for terminal statuses
        if job.status in (JobStatus.COMPLETED, JobStatus.FAILED):
            metadata.completed_at = time.time()

        self._on_status_update(job.id, job.status, metadata)

        # Record benchmark timing for both start (end_time=-1) and end notifications
        if self._benchmark and job.start_time != -1:
            phase_name = STATUS_TO_BENCHMARK.get(job.status)
            if phase_name:
                self._benchmark.record(job.id, phase_name, job.start_time, job.end_time)

        if self._benchmark and job.status == JobStatus.COMPLETED:
            aggregates = self._benchmark.get_aggregates()
            logger.info(
                "Benchmark [%s]: jobs=%d, fetch_avg_ms=%.2f, download_avg_ms=%.2f, "
                "merge_avg_ms=%.2f, upload_avg_ms=%.2f, peak_memory_mb=%.2f",
                job.id,
                aggregates.total_job_count,
                aggregates.avg_time_per_phase.get(BenchmarkPhase.FETCHING, 0)
                / 1_000_000,
                aggregates.avg_time_per_phase.get(BenchmarkPhase.DOWNLOADING, 0)
                / 1_000_000,
                aggregates.avg_time_per_phase.get(BenchmarkPhase.MERGING, 0)
                / 1_000_000,
                aggregates.avg_time_per_phase.get(BenchmarkPhase.UPLOADING, 0)
                / 1_000_000,
                aggregates.peak_memory_mb,
            )

    def stop(self) -> None:
        """Stop the notification worker."""
        self._running = False
