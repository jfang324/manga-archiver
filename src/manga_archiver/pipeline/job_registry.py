import time
from collections import deque
from collections.abc import Callable

from ..constants.defaults import DEFAULT_JOB_EXPIRY_SECONDS
from ..workers.jobs import FetchingResourcesJob
from ..workers.types import JobMetadata, JobStatus

TERMINAL_STATUSES = frozenset({JobStatus.COMPLETED, JobStatus.FAILED})


class PipelineJobRegistry:
    """Tracks pipeline job status, retry state, and terminal job expiry."""

    def __init__(
        self,
        job_expiry_seconds: int = DEFAULT_JOB_EXPIRY_SECONDS,
        time_provider: Callable[[], float] = time.time,
    ) -> None:
        """Initialize the registry."""
        self._job_statuses: dict[str, tuple[JobStatus, JobMetadata]] = {}
        self._failed_jobs: dict[str, FetchingResourcesJob] = {}
        self._job_expiry_queue: deque[tuple[float, str]] = deque()
        self._job_expiry_seconds = job_expiry_seconds
        self._time_provider = time_provider

    def record_status_update(self, job_id: str, status: JobStatus, metadata: JobMetadata) -> None:
        """Record a status update and expire old terminal jobs."""
        self._job_statuses[job_id] = (status, metadata)

        if status == JobStatus.FAILED:
            self._failed_jobs[job_id] = FetchingResourcesJob(
                id=job_id,
                manga_title=metadata.manga_title,
                chapter_id=metadata.chapter_id,
                chapter_number=metadata.chapter_number,
                chapter_title=metadata.chapter_title,
                app_config=metadata.app_config,
                source=metadata.source,
            )

        if status == JobStatus.COMPLETED:
            self._failed_jobs.pop(job_id, None)

        if status in TERMINAL_STATUSES:
            self._job_expiry_queue.append((self._time_provider(), job_id))

        self._expire_jobs()

    def get_jobs(self) -> dict[str, tuple[JobStatus, JobMetadata]]:
        """Return a copy of the current job statuses."""
        return self._job_statuses.copy()

    def incomplete_job_count(self) -> int:
        """Return the number of jobs not in a terminal state."""
        return sum(
            1 for status, _ in self._job_statuses.values() if status not in TERMINAL_STATUSES
        )

    def pop_failed_jobs(self) -> list[FetchingResourcesJob]:
        """Return and clear failed jobs available for retry."""
        jobs = list(self._failed_jobs.values())
        self._failed_jobs.clear()

        return jobs

    def _expire_jobs(self) -> None:
        """Remove terminal jobs that have aged past the expiry window."""
        now = self._time_provider()

        while self._job_expiry_queue:
            oldest_timestamp, oldest_job_id = self._job_expiry_queue[0]

            if now - oldest_timestamp < self._job_expiry_seconds:
                break

            self._job_expiry_queue.popleft()
            self._job_statuses.pop(oldest_job_id, None)
