import asyncio
import logging
import time
from asyncio import Queue, QueueEmpty
from collections import deque
from dataclasses import dataclass

from ..models import ContentSource
from .jobs import Job

logger = logging.getLogger(__name__)

MAX_DRAIN_PER_TICK = 500


@dataclass(frozen=True)
class SchedulerConfig:
    """Configuration for rate-limit-aware job scheduling."""

    acceptance_threshold: float = 0.15
    window_size: int = 20
    expiry_seconds: float = 120.0
    max_skips: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.acceptance_threshold <= 1:
            raise ValueError("acceptance_threshold must be greater than 0 and at most 1")

        if self.window_size < 1:
            raise ValueError("window_size must be greater than 0")

        if self.expiry_seconds <= 0:
            raise ValueError("expiry_seconds must be greater than 0")

        if self.max_skips < 1:
            raise ValueError("max_skips must be greater than 0")


@dataclass(frozen=True)
class SchedulerFeedback:
    """Result feedback used to calculate per-source rate-limit risk."""

    source: ContentSource
    was_rate_limited: bool
    timestamp: float


class RateLimitAwareScheduler:
    """Soft-prioritizes jobs using recent per-source rate-limit feedback."""

    def __init__(
        self,
        input_queue: Queue[Job],
        output_queue: Queue[Job],
        feedback_queue: Queue[SchedulerFeedback],
        config: SchedulerConfig,
    ) -> None:
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._feedback_queue = feedback_queue
        self._config = config

        self._pending_by_source: dict[ContentSource, deque[Job]] = {}
        self._skip_count_by_source: dict[ContentSource, int] = {}
        self._feedback_history: dict[ContentSource, deque[SchedulerFeedback]] = {}
        self._sources: list[ContentSource] = []
        self._source_index = 0
        self._running = False
        self._next_log_time = 0.0

    async def run(self) -> None:
        """Run the scheduling loop."""
        self._running = True

        while self._running:
            try:
                self._drain_feedback()
                self._drain_input()

                if not self._has_other_pending_source():
                    try:
                        job = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue

                    self._add_pending_job(job)
                    self._input_queue.task_done()
                    continue

                await self._schedule_next_job()
            except asyncio.CancelledError:
                self._running = False
                break

    def stop(self) -> None:
        """Stop the scheduler."""
        self._running = False

    def _drain_input(self) -> None:
        """Drain input queue into per-source pending queues."""
        for _ in range(MAX_DRAIN_PER_TICK):
            if not self._running:
                break

            try:
                job = self._input_queue.get_nowait()
            except QueueEmpty:
                return

            self._add_pending_job(job)
            self._input_queue.task_done()

    def _drain_feedback(self) -> None:
        """Drain feedback queue into in-memory history."""
        for _ in range(MAX_DRAIN_PER_TICK):
            if not self._running:
                break

            try:
                feedback = self._feedback_queue.get_nowait()
            except QueueEmpty:
                return

            history = self._feedback_history.setdefault(
                feedback.source,
                deque(maxlen=self._config.window_size),
            )
            history.append(feedback)
            self._feedback_queue.task_done()

    async def _schedule_next_job(self) -> None:
        """Schedule next job based on thresholds and history."""
        if not self._sources:
            await asyncio.sleep(0)
            return

        source = self._sources[self._source_index]
        self._source_index = (self._source_index + 1) % len(self._sources)

        source_jobs = self._pending_by_source.get(source)
        if not source_jobs:
            await asyncio.sleep(0)
            return

        required_skips = self._required_skips(source)
        current_skips = self._skip_count_by_source[source]

        if current_skips < required_skips and self._has_other_pending_source(source):
            self._skip_count_by_source[source] = current_skips + 1
            logger.debug(
                "Scheduler skipped hot source %s; risk %.2f skip=%d/%d pending=%d",
                source,
                self._rate_limit_percentage(source),
                current_skips + 1,
                required_skips,
                self._pending_count(),
            )
            await asyncio.sleep(0)
            return

        job = source_jobs[0]
        dispatched = False
        while self._running and not dispatched:
            try:
                await asyncio.wait_for(self._output_queue.put(job), timeout=0.5)
                dispatched = True
            except asyncio.TimeoutError:  # noqa: PERF203
                continue

        if not dispatched:
            return

        source_jobs.popleft()
        self._skip_count_by_source[source] = 0

        await asyncio.sleep(0)

        logger.debug(
            "Scheduler dispatched job %s for source %s; risk %.2f skips=%d/%d "
            "pending=%d output_queue=%d",
            job.id,
            source,
            self._rate_limit_percentage(source),
            current_skips,
            required_skips,
            self._pending_count(),
            self._output_queue.qsize(),
        )

    def _add_pending_job(self, job: Job) -> None:
        """Add job to its source queue and track source."""
        source_jobs = self._pending_by_source.setdefault(job.source, deque())
        source_jobs.append(job)
        self._skip_count_by_source.setdefault(job.source, 0)

        if job.source not in self._sources:
            self._sources.append(job.source)

    def _has_other_pending_source(self, source: ContentSource | None = None) -> bool:
        """Check for pending jobs.

        If source is None: return whether ANY source has pending jobs.
        If source is provided: return whether ANY OTHER source has pending jobs.
        """
        if source is None:
            return any(self._pending_by_source.values())
        return any(s != source and bool(jobs) for s, jobs in self._pending_by_source.items())

    def _pending_count(self) -> int:
        """Return total pending job count."""
        return sum(len(source_jobs) for source_jobs in self._pending_by_source.values())

    def _required_skips(self, source: ContentSource) -> int:
        """Expire outdated feedback and calculate required skips based on risk."""
        now = time.monotonic()
        self._expire_feedback(now)

        risk = self._rate_limit_percentage(source)
        if risk < self._config.acceptance_threshold:
            return 0

        return min(
            self._config.max_skips,
            int(risk / self._config.acceptance_threshold),
        )

    def _rate_limit_percentage(self, source: ContentSource) -> float:
        """Calculate rate limit percentage for a source."""
        history = self._feedback_history.get(source)
        if not history:
            return 0

        rate_limit_count = sum(1 for event in history if event.was_rate_limited)
        return rate_limit_count / self._config.window_size

    def _expire_feedback(self, now: float) -> None:
        """Expire feedback history based on expiry time."""
        expiry_cutoff = now - self._config.expiry_seconds

        for source, history in list(self._feedback_history.items()):
            while history and history[0].timestamp < expiry_cutoff:
                history.popleft()

            if not history:
                del self._feedback_history[source]
