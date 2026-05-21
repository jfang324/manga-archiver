import tracemalloc
from dataclasses import dataclass
from pathlib import Path
from typing import TypeAlias, TypedDict

from ..workers.jobs import JobStatus

NANOSECONDS_PER_MILLISECOND = 1_000_000
BYTES_PER_MEGABYTE = 1024 * 1024

BenchmarkReport: TypeAlias = dict[str, float | int]


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
        if not tracemalloc.is_tracing():
            tracemalloc.start()

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
        _, peak = tracemalloc.get_traced_memory()
        return peak / BYTES_PER_MEGABYTE

    def _aggregate_metrics(self) -> BenchmarkAggregates:
        """Aggregate all recorded benchmark metrics in one pass."""
        total_time_per_phase: dict[JobStatus, int] = dict.fromkeys(self._TRACKED_PHASES, 0)
        count_per_phase: dict[JobStatus, int] = dict.fromkeys(self._TRACKED_PHASES, 0)
        total_times: list[int] = []
        earliest_resolve: float | None = None
        latest_merge: float = 0
        latest_upload: float = 0

        for metric in self._metrics.values():
            job_total = 0
            timings = metric["timings"]

            for phase in self._TRACKED_PHASES:
                phase_timings = timings.get(phase)
                if phase_timings is None:
                    continue

                start_ns = phase_timings["start_ns"]
                end_ns = phase_timings["end_ns"]
                if start_ns is None or end_ns is None:
                    continue

                duration = int(end_ns - start_ns)
                total_time_per_phase[phase] += duration
                count_per_phase[phase] += 1
                job_total += duration

            if job_total > 0:
                total_times.append(job_total)

            fetching = timings.get(JobStatus.FETCHING_RESOURCES)
            fetching_start_ns = fetching["start_ns"] if fetching else None
            if fetching_start_ns is not None and (
                earliest_resolve is None or fetching_start_ns < earliest_resolve
            ):
                earliest_resolve = fetching_start_ns

            merging = timings.get(JobStatus.MERGING)
            merging_end_ns = merging["end_ns"] if merging else None
            if merging_end_ns is not None and merging_end_ns > latest_merge:
                latest_merge = merging_end_ns

            uploading = timings.get(JobStatus.UPLOADING)
            uploading_end_ns = uploading["end_ns"] if uploading else None
            if uploading_end_ns is not None and uploading_end_ns > latest_upload:
                latest_upload = uploading_end_ns

        avg_time_per_phase = {
            phase: total_time_per_phase[phase] // count_per_phase[phase]
            if count_per_phase[phase] > 0
            else 0
            for phase in self._TRACKED_PHASES
        }
        avg_total_time = sum(total_times) // len(total_times) if total_times else 0
        highest_download = (
            int(latest_merge - earliest_resolve)
            if earliest_resolve is not None and latest_merge > 0
            else 0
        )
        highest_e2e = (
            int(latest_upload - earliest_resolve)
            if earliest_resolve is not None and latest_upload > 0
            else 0
        )

        return BenchmarkAggregates(
            total_time_per_phase=total_time_per_phase,
            avg_time_per_phase=avg_time_per_phase,
            avg_total_time=avg_total_time,
            peak_memory_mb=self._get_memory(),
            total_job_count=len(self._metrics),
            highest_perceived_download_time=highest_download,
            highest_perceived_end_to_end=highest_e2e,
        )

    def get_aggregates(self) -> BenchmarkAggregates:
        """Calculate aggregate metrics from all recorded jobs."""
        return self._aggregate_metrics()


PHASE_REPORT_PREFIXES: tuple[tuple[JobStatus, str], ...] = (
    (JobStatus.FETCHING_RESOURCES, "fetching"),
    (JobStatus.DOWNLOADING, "downloading"),
    (JobStatus.MERGING, "merging"),
    (JobStatus.UPLOADING, "uploading"),
)


def format_benchmark_results(aggregates: BenchmarkAggregates) -> BenchmarkReport:
    """Convert aggregate benchmark metrics to report-ready values."""
    report: BenchmarkReport = {
        "total_job_count": aggregates.total_job_count,
    }

    for phase, prefix in PHASE_REPORT_PREFIXES:
        report[f"{prefix}_total_ms"] = (
            aggregates.total_time_per_phase.get(phase, 0) / NANOSECONDS_PER_MILLISECOND
        )
        report[f"{prefix}_avg_ms"] = (
            aggregates.avg_time_per_phase.get(phase, 0) / NANOSECONDS_PER_MILLISECOND
        )

    report.update(
        {
            "avg_total_time_ms": aggregates.avg_total_time / NANOSECONDS_PER_MILLISECOND,
            "peak_memory_mb": aggregates.peak_memory_mb,
            "highest_perceived_download_time_ms": aggregates.highest_perceived_download_time
            / NANOSECONDS_PER_MILLISECOND,
            "highest_perceived_end_to_end_ms": aggregates.highest_perceived_end_to_end
            / NANOSECONDS_PER_MILLISECOND,
        }
    )

    return report


def write_benchmark_report(benchmark_results: BenchmarkReport | None) -> None:
    """Write benchmark results to disk."""
    if not benchmark_results:
        return

    benchmark_dir = Path("~/.manga-archiver/benchmark").expanduser()
    metrics_file = benchmark_dir / "metrics.txt"

    benchmark_dir.mkdir(parents=True, exist_ok=True)

    with metrics_file.open("w") as f:
        f.write("Benchmark Results\n")
        f.write("=" * 40 + "\n")
        for key, value in benchmark_results.items():
            if "ms" in key:
                f.write(f"{key}: {value:.2f} ms\n")
            elif "memory" in key:
                f.write(f"{key}: {value:.2f} MB\n")
            else:
                f.write(f"{key}: {value}\n")
