from asyncio import Queue
from typing import Callable

from ..enums import JobStatus
from .base import Worker, WorkerConfig
from .jobs import Job, NotificationJob


class BenchmarkWorker(Worker):
    """Worker that tracks job timing across the pipeline for benchmarking."""

    def __init__(
        self,
        id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        expected_count: int | None = None,
        benchmark_callback: Callable[[float, float], None] | None = None,
    ):
        """
        Initialize the benchmark worker.

        Args:
            id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            expected_count: Number of jobs expected in the benchmark
            benchmark_callback: Callback to invoke with (earliest_start, latest_end) when complete
            config: The configuration for the worker
        """
        super().__init__(id, input_queue, output_queue, config, notification_queue)

        self._expected_count = expected_count
        self._benchmark_callback = benchmark_callback
        self._job_timings: list[tuple[float, float]] = []

    async def _do_work(self, job: Job) -> None:
        """Track job timing and report when all jobs complete.

        Args:
            job: The completed job to track
        """
        if job.start_time != -1 and job.end_time != -1:
            self._job_timings.append((job.start_time, job.end_time))

        await self._notification_queue.put(
            NotificationJob(
                id=job.id,
                manga_title=job.manga_title,
                chapter_title=job.chapter_title,
                output_directory=job.output_directory,
                output_format=job.output_format,
                start_time=job.start_time,
                end_time=job.end_time,
                status=JobStatus.COMPLETED,
            )
        )

        if (
            self._expected_count is not None
            and len(self._job_timings) >= self._expected_count
        ):
            self._report_benchmark()

    def _report_benchmark(self) -> None:
        """Report the time elapsed between the first and last jobs."""
        if not self._job_timings:
            return

        earliest: float = min(t[0] for t in self._job_timings)
        latest: float = max(t[1] for t in self._job_timings)

        if self._benchmark_callback:
            self._benchmark_callback(earliest, latest)
