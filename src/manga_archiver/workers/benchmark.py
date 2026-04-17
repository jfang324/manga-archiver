import tracemalloc
from dataclasses import dataclass
from typing import TypedDict

from ..workers.jobs import JobStatus


class PhaseTimings(TypedDict):
    """Stores start and end timestamps for a single phase."""

    start_ns: float | None
    end_ns: float | None


class BenchmarkMetric(TypedDict):
    """Stores timing timestamps for a single job.

    Attributes:
        timings: Dictionary mapping JobStatus to (start, end) timestamps
    """

    timings: dict[JobStatus, PhaseTimings]


@dataclass
class BenchmarkAggregates:
    """Aggregate benchmark metrics across all jobs.

    Attributes:
        total_time_per_phase: Total time in nanoseconds per phase
        avg_time_per_phase: Average time in nanoseconds per phase
        avg_total_time: Average total time across all jobs in nanoseconds
        peak_memory_mb: Peak application memory in megabytes
        total_job_count: Total number of jobs processed
        highest_perceived_download_time: Max time from earliest resolve start to latest merge end
        highest_perceived_end_to_end: Max time from earliest resolve start to latest upload end
    """

    total_time_per_phase: dict[JobStatus, int]
    avg_time_per_phase: dict[JobStatus, int]
    avg_total_time: int
    peak_memory_mb: float
    total_job_count: int
    highest_perceived_download_time: int
    highest_perceived_end_to_end: int


class BenchmarkManager:
    """Manages benchmark metrics collection and aggregation.

    Stores timing data for each job and calculates aggregate metrics
    when requested.
    """

    _TRACKED_PHASES: tuple[JobStatus, ...] = (
        JobStatus.FETCHING_RESOURCES,
        JobStatus.DOWNLOADING,
        JobStatus.MERGING,
        JobStatus.UPLOADING,
    )

    def __init__(self) -> None:
        self._metrics: dict[str, BenchmarkMetric] = {}

    def record(self, job_id: str, status: JobStatus, start_ns: float, end_ns: float) -> None:
        """Record timing for a job phase.

        Args:
            job_id: Unique identifier for the job
            status: The JobStatus phase (e.g., JobStatus.DOWNLOADING)
            start_ns: Start time in nanoseconds
            end_ns: End time in nanoseconds (-1 if phase just started)
        """
        if status not in self._TRACKED_PHASES:
            return

        metric = self._metrics.setdefault(job_id, {"timings": {}})
        metric["timings"][status] = {
            "start_ns": start_ns if start_ns != -1 else None,
            "end_ns": end_ns if end_ns != -1 else None,
        }

    def _get_memory(self) -> float:
        """Get peak memory in MB using tracemalloc."""
        _, current = tracemalloc.get_traced_memory()
        return current / (1024 * 1024)

    def _calculate_phase_times(
        self,
    ) -> tuple[dict[JobStatus, int], dict[JobStatus, int], list[int]]:
        """Calculate timing aggregates per phase.

        Returns:
            Tuple of (total_time_per_phase, count_per_phase, total_times_per_job)
        """
        total_time_per_phase = dict.fromkeys(self._TRACKED_PHASES, 0)
        count_per_phase = dict.fromkeys(self._TRACKED_PHASES, 0)
        total_times: list[int] = []

        for metric in self._metrics.values():
            job_total = 0
            timings = metric["timings"]

            for phase in self._TRACKED_PHASES:
                phase_timings = timings.get(phase)
                if phase_timings and phase_timings["start_ns"] and phase_timings["end_ns"]:
                    duration = int(phase_timings["end_ns"] - phase_timings["start_ns"])
                    total_time_per_phase[phase] += duration
                    count_per_phase[phase] += 1
                    job_total += duration

            if job_total > 0:
                total_times.append(job_total)

        return total_time_per_phase, count_per_phase, total_times

    def _calculate_global_markers(self) -> tuple[float | None, float, float]:
        """Calculate global timing markers across all jobs.

        Returns:
            Tuple of (earliest_resolve, latest_merge, latest_upload)
        """
        earliest_resolve: float | None = None
        latest_merge: float = 0
        latest_upload: float = 0

        for metric in self._metrics.values():
            timings = metric["timings"]

            # Track earliest resolve (FETCHING_RESOURCES start)
            fetching = timings.get(JobStatus.FETCHING_RESOURCES)
            if (
                fetching
                and fetching["start_ns"]
                and (earliest_resolve is None or fetching["start_ns"] < earliest_resolve)
            ):
                earliest_resolve = fetching["start_ns"]

            # Track latest merge end
            merging = timings.get(JobStatus.MERGING)
            if merging and merging["end_ns"] and merging["end_ns"] > latest_merge:
                latest_merge = merging["end_ns"]

            # Track latest upload end
            uploading = timings.get(JobStatus.UPLOADING)
            if uploading and uploading["end_ns"] and uploading["end_ns"] > latest_upload:
                latest_upload = uploading["end_ns"]

        return earliest_resolve, latest_merge, latest_upload

    def _compute_averages(
        self, total_time: dict[JobStatus, int], count: dict[JobStatus, int]
    ) -> dict[JobStatus, int]:
        """Compute average times per phase.

        Args:
            total_time: Total time per phase
            count: Count of jobs per phase

        Returns:
            Dictionary of average times per phase
        """
        return {
            phase: total_time[phase] // count[phase] if count[phase] > 0 else 0
            for phase in self._TRACKED_PHASES
        }

    def _compute_avg_total(self, total_times: list[int]) -> int:
        """Compute average total time across all jobs.

        Args:
            total_times: List of total times per job

        Returns:
            Average total time in nanoseconds
        """
        return sum(total_times) // len(total_times) if total_times else 0

    def _compute_highest_times(
        self, earliest_resolve: float | None, latest_merge: float, latest_upload: float
    ) -> tuple[int, int]:
        """Compute highest perceived times.

        Args:
            earliest_resolve: Earliest resolve start time
            latest_merge: Latest merge end time
            latest_upload: Latest upload end time

        Returns:
            Tuple of (highest_perceived_download_time, highest_perceived_end_to_end)
        """
        highest_download = 0
        if earliest_resolve is not None and latest_merge > 0:
            highest_download = int(latest_merge - earliest_resolve)

        highest_e2e = 0
        if earliest_resolve is not None and latest_upload > 0:
            highest_e2e = int(latest_upload - earliest_resolve)

        return highest_download, highest_e2e

    def get_aggregates(self) -> BenchmarkAggregates:
        """Calculate aggregate metrics from all recorded jobs."""
        peak_memory_mb = self._get_memory()
        total_time_per_phase, count_per_phase, total_times = self._calculate_phase_times()
        earliest_resolve, latest_merge, latest_upload = self._calculate_global_markers()

        avg_time_per_phase = self._compute_averages(total_time_per_phase, count_per_phase)
        avg_total = self._compute_avg_total(total_times)
        highest_download, highest_e2e = self._compute_highest_times(
            earliest_resolve, latest_merge, latest_upload
        )

        return BenchmarkAggregates(
            total_time_per_phase=total_time_per_phase,
            avg_time_per_phase=avg_time_per_phase,
            avg_total_time=avg_total,
            peak_memory_mb=peak_memory_mb,
            total_job_count=len(self._metrics),
            highest_perceived_download_time=highest_download,
            highest_perceived_end_to_end=highest_e2e,
        )
