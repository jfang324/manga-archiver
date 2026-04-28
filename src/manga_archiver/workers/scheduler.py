import asyncio
import logging
import time
from asyncio import Queue, QueueEmpty
from collections import deque
from dataclasses import dataclass

from ..models import ContentSource
from .jobs import Job

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SchedulerConfig:
    """Configuration for rate-limit-aware job scheduling."""

    acceptance_threshold: float = 0.15
    window_size: int = 20
    expiry_seconds: float = 120.0
    log_interval_seconds: float = 5.0
    max_skips: int = 2

    def __post_init__(self) -> None:
        if not 0 < self.acceptance_threshold <= 1:
            raise ValueError("acceptance_threshold must be greater than 0 and at most 1")

        if self.window_size < 1:
            raise ValueError("window_size must be greater than 0")

        if self.expiry_seconds <= 0:
            raise ValueError("expiry_seconds must be greater than 0")

        if self.log_interval_seconds <= 0:
            raise ValueError("log_interval_seconds must be greater than 0")

        if self.max_skips < 1:
            raise ValueError("max_skips must be greater than 0")


@dataclass(frozen=True)
class SchedulerFeedback:
    """Result feedback used to calculate per-source rate-limit risk."""

    source: ContentSource
    was_rate_limited: bool
    timestamp: float


@dataclass
class _QueuedJob:
    """Container for queued jobs with skip count."""

    job: Job
    skip_count: int = 0


MAX_DRAIN_PER_TICK = 500


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

        self._pending_jobs: deque[_QueuedJob] = deque()
        self._feedback_history: dict[ContentSource, deque[SchedulerFeedback]] = {}
        self._running = False
        self._next_log_time = 0.0

    async def run(self) -> None:
        """Run the scheduling loop."""
        self._running = True

        while self._running:
            try:
                self._drain_feedback()
                self._drain_input()
                self._log_snapshot()

                if not self._pending_jobs:
                    try:
                        job = await asyncio.wait_for(self._input_queue.get(), timeout=0.5)
                    except asyncio.TimeoutError:
                        continue

                    self._pending_jobs.append(_QueuedJob(job))
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
        """Drain input queue into in-memory deque."""
        for _ in range(MAX_DRAIN_PER_TICK):
            if not self._running:
                break

            try:
                job = self._input_queue.get_nowait()
            except QueueEmpty:
                return

            self._pending_jobs.append(_QueuedJob(job))
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
        queued_job = self._pending_jobs[0]
        source = queued_job.job.source
        required_skips = self._required_skips(source)

        if queued_job.skip_count < required_skips:
            queued_job.skip_count += 1
            logger.debug(
                "Scheduler requeued job %s for source %s; risk %.2f skip=%d/%d",
                queued_job.job.id,
                source,
                self._rate_limit_percentage(source),
                queued_job.skip_count,
                required_skips,
            )
            self._pending_jobs.append(self._pending_jobs.popleft())
            # Yield so repeated skips do not monopolize the event loop.
            await asyncio.sleep(0)
            return

        await self._output_queue.put(queued_job.job)
        self._pending_jobs.popleft()
        # Yield so repeated skips do not monopolize the event loop.
        await asyncio.sleep(0)

        logger.debug(
            "Scheduler dispatched job %s for source %s; risk %.2f skips=%d/%d pending=%d "
            "output_queue=%d",
            queued_job.job.id,
            source,
            self._rate_limit_percentage(source),
            queued_job.skip_count,
            required_skips,
            len(self._pending_jobs),
            self._output_queue.qsize(),
        )

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

    def _log_snapshot(self) -> None:
        """Log snapshot of pending jobs and skip counts."""
        now = time.monotonic()
        if now < self._next_log_time:
            return

        self._next_log_time = now + self._config.log_interval_seconds

        pending_by_source: dict[ContentSource, int] = {}
        skipped_count = 0

        for queued_job in self._pending_jobs:
            pending_by_source[queued_job.job.source] = (
                pending_by_source.get(queued_job.job.source, 0) + 1
            )
            if queued_job.skip_count > 0:
                skipped_count += 1

        risk_by_source = {
            source: round(self._rate_limit_percentage(source), 2)
            for source in sorted(self._feedback_history, key=lambda item: item.value)
        }

        logger.debug(
            "Scheduler snapshot: pending=%d by_source=%s skipped=%d output_queue=%d "
            "feedback_queue=%d risk=%s",
            len(self._pending_jobs),
            pending_by_source,
            skipped_count,
            self._output_queue.qsize(),
            self._feedback_queue.qsize(),
            risk_by_source,
        )
