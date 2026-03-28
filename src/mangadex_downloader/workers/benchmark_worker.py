import logging
from typing import Callable

from .base import Worker
from .jobs import Job

logger = logging.getLogger(__name__)


class BenchmarkWorker(Worker):
    """Worker that tracks job timing across the pipeline for benchmarking."""

    def __init__(
        self,
        expected_count: int | None = None,
        benchmark_callback: Callable[[float, float], None] | None = None,
        **kwargs,
    ):
        """Initialize the benchmark worker.

        Args:
            expected_count: Number of jobs expected in the benchmark
            benchmark_callback: Callback to invoke with (earliest_start, latest_end) when complete
        """
        super().__init__(**kwargs)
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

        if (
            self._expected_count is not None
            and len(self._job_timings) >= self._expected_count
        ):
            self._report_benchmark()

    def _report_benchmark(self) -> None:
        """Calculate and report benchmark results."""
        if not self._job_timings:
            return

        earliest: float = min(t[0] for t in self._job_timings)
        latest: float = max(t[1] for t in self._job_timings)

        if self._benchmark_callback:
            self._benchmark_callback(earliest, latest)
