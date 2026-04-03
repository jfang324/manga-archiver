import tracemalloc
from dataclasses import dataclass
from enum import Enum
from typing import NamedTuple


class BenchmarkPhase(Enum):
    """Phases of the pipeline for benchmarking."""

    FETCHING = "fetching"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    UPLOADING = "uploading"


class Timestamps(NamedTuple):
    """Stores attribute names for start/end timestamps of a phase."""

    start: str
    end: str


class BenchmarkMetric:
    """Stores timing timestamps for a single job.

    Attributes:
        job_id: Unique identifier for the job
        resolve_start_ns: Start time of resolve phase (nanoseconds) or None
        resolve_end_ns: End time of resolve phase (nanoseconds) or None
        download_start_ns: Start time of download phase (nanoseconds) or None
        download_end_ns: End time of download phase (nanoseconds) or None
        merge_start_ns: Start time of merge phase (nanoseconds) or None
        merge_end_ns: End time of merge phase (nanoseconds) or None
        upload_start_ns: Start time of upload phase (nanoseconds) or None
        upload_end_ns: End time of upload phase (nanoseconds) or None
    """

    __slots__ = (
        "job_id",
        "resolve_start_ns",
        "resolve_end_ns",
        "download_start_ns",
        "download_end_ns",
        "merge_start_ns",
        "merge_end_ns",
        "upload_start_ns",
        "upload_end_ns",
    )

    job_id: str
    resolve_start_ns: float | None
    resolve_end_ns: float | None
    download_start_ns: float | None
    download_end_ns: float | None
    merge_start_ns: float | None
    merge_end_ns: float | None
    upload_start_ns: float | None
    upload_end_ns: float | None

    def __init__(
        self,
        job_id: str,
        resolve_start_ns: float | None = None,
        resolve_end_ns: float | None = None,
        download_start_ns: float | None = None,
        download_end_ns: float | None = None,
        merge_start_ns: float | None = None,
        merge_end_ns: float | None = None,
        upload_start_ns: float | None = None,
        upload_end_ns: float | None = None,
    ) -> None:
        self.job_id = job_id
        self.resolve_start_ns = resolve_start_ns
        self.resolve_end_ns = resolve_end_ns
        self.download_start_ns = download_start_ns
        self.download_end_ns = download_end_ns
        self.merge_start_ns = merge_start_ns
        self.merge_end_ns = merge_end_ns
        self.upload_start_ns = upload_start_ns
        self.upload_end_ns = upload_end_ns


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

    total_time_per_phase: dict[BenchmarkPhase, int]
    avg_time_per_phase: dict[BenchmarkPhase, int]
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

    _phase_fields: dict[BenchmarkPhase, Timestamps] = {
        BenchmarkPhase.FETCHING: Timestamps("resolve_start_ns", "resolve_end_ns"),
        BenchmarkPhase.DOWNLOADING: Timestamps("download_start_ns", "download_end_ns"),
        BenchmarkPhase.MERGING: Timestamps("merge_start_ns", "merge_end_ns"),
        BenchmarkPhase.UPLOADING: Timestamps("upload_start_ns", "upload_end_ns"),
    }

    def __init__(self) -> None:
        self._metrics: dict[str, BenchmarkMetric] = {}
        self._peak_memory_bytes: int = 0

    def _parse_phase(self, status: str) -> BenchmarkPhase | None:
        """Convert status string to BenchmarkPhase.

        Args:
            status: Status string (e.g., 'fetching_resources', 'downloading')

        Returns:
            BenchmarkPhase or None if invalid
        """
        key = status.replace("_resources", "")
        try:
            return BenchmarkPhase(key)
        except ValueError:
            return None

    def record(self, job_id: str, status: str, start_ns: float, end_ns: float) -> None:
        """Record timing for a job phase.

        Args:
            job_id: Unique identifier for the job
            status: The status/phase name (e.g., 'fetching_resources', 'downloading')
            start_ns: Start time in nanoseconds
            end_ns: End time in nanoseconds (or None if phase just started)
        """
        phase = self._parse_phase(status)
        if phase is None:
            return

        metric = self._metrics.get(job_id)
        if metric is None:
            metric = BenchmarkMetric(job_id=job_id)
            self._metrics[job_id] = metric

        timestamps = self._phase_fields[phase]
        setattr(metric, timestamps.start, start_ns)
        setattr(metric, timestamps.end, end_ns if end_ns != -1 else None)

    def record_memory(self, memory_bytes: int) -> None:
        """Record peak memory usage.

        Args:
            memory_bytes: Current memory usage in bytes
        """
        self._peak_memory_bytes = max(self._peak_memory_bytes, memory_bytes)

    def _get_duration(self, metric: BenchmarkMetric, phase: BenchmarkPhase) -> int:
        """Get duration in nanoseconds for a phase, or 0 if not complete."""
        timestamps = self._phase_fields[phase]
        start = getattr(metric, timestamps.start)
        end = getattr(metric, timestamps.end)
        if start is not None and end is not None:
            return int(end - start)
        return 0

    def _update_markers(
        self,
        metric: BenchmarkMetric,
        earliest_resolve: float | None,
        latest_merge: float,
        latest_upload: float,
    ) -> tuple[float | None, float, float]:
        """Update global timing markers from a single metric."""
        if metric.resolve_start_ns is not None and (
            earliest_resolve is None or metric.resolve_start_ns < earliest_resolve
        ):
            earliest_resolve = metric.resolve_start_ns
        if metric.merge_end_ns is not None and metric.merge_end_ns > latest_merge:
            latest_merge = metric.merge_end_ns
        if metric.upload_end_ns is not None and metric.upload_end_ns > latest_upload:
            latest_upload = metric.upload_end_ns
        return earliest_resolve, latest_merge, latest_upload

    def get_aggregates(self) -> BenchmarkAggregates:
        """Calculate aggregate metrics from all recorded jobs."""
        if self._peak_memory_bytes == 0:
            _, self._peak_memory_bytes = tracemalloc.get_traced_memory()

        peak_memory_mb = self._peak_memory_bytes / (1024 * 1024)

        total_time_per_phase = dict.fromkeys(self._phase_fields, 0)
        count_per_phase = dict.fromkeys(self._phase_fields, 0)

        total_times: list[int] = []
        earliest_resolve: float | None = None
        latest_merge: float = 0
        latest_upload: float = 0

        for metric in self._metrics.values():
            job_total = 0

            for phase in self._phase_fields:
                duration = self._get_duration(metric, phase)
                if duration > 0:
                    total_time_per_phase[phase] += duration
                    count_per_phase[phase] += 1
                    job_total += duration

            earliest_resolve, latest_merge, latest_upload = self._update_markers(
                metric, earliest_resolve, latest_merge, latest_upload
            )

            if job_total > 0:
                total_times.append(job_total)

        avg_time_per_phase = {
            phase: (total_time_per_phase[phase] // count_per_phase[phase])
            if count_per_phase[phase] > 0
            else 0
            for phase in self._phase_fields
        }

        avg_total = sum(total_times) // len(total_times) if total_times else 0

        highest_download = 0
        if earliest_resolve is not None and latest_merge > 0:
            highest_download = int(latest_merge - earliest_resolve)

        highest_e2e = 0
        if earliest_resolve is not None and latest_upload > 0:
            highest_e2e = int(latest_upload - earliest_resolve)

        return BenchmarkAggregates(
            total_time_per_phase=total_time_per_phase,
            avg_time_per_phase=avg_time_per_phase,
            avg_total_time=avg_total,
            peak_memory_mb=peak_memory_mb,
            total_job_count=len(self._metrics),
            highest_perceived_download_time=highest_download,
            highest_perceived_end_to_end=highest_e2e,
        )
