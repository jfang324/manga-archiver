import asyncio
import logging
import random
import time
from abc import ABC, abstractmethod
from asyncio import CancelledError, Queue
from dataclasses import dataclass

from aiohttp import ClientError

from ..integrations.exceptions import (
    BadGatewayError,
    NotFoundError,
    RateLimitError,
)
from .jobs import Job, JobStatus, NotificationJob
from .scheduler import SchedulerFeedback

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class WorkerConfig:
    """Immutable data container for the configuration of a worker.

    Attributes:
        max_retries (int): The maximum number of retries for failed downloads
        base_delay (int): The base delay in seconds between retries
        jitter (bool): Whether to apply jitter to the delay between retries
        await_output_space (bool): Whether to check the output queue for space before processing.
    """

    max_retries: int = 5
    base_delay: int = 5
    jitter: bool = False
    await_output_space: bool = False  # currently no way to set, still testing performance impact


class Worker(ABC):
    """Base class for async pipeline workers that process jobs with retry logic.

    Workers operate in a continuous loop pulling jobs from an input queue, processing them,
    and optionally passing them to an output queue. Implements configurable retry with
    exponential backoff for different error types.
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        config: WorkerConfig,
        notification_queue: Queue[NotificationJob],
        work_status: JobStatus,
        scheduler_feedback_queue: Queue[SchedulerFeedback] | None = None,
    ) -> None:
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            config: The configuration for the worker
            notification_queue: The queue for notification jobs
            work_status: The active status represented by this worker phase
            scheduler_feedback_queue: Optional queue for scheduler result feedback
        """
        self._id = worker_id
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._notification_queue = notification_queue
        self._work_status = work_status
        self._scheduler_feedback_queue = scheduler_feedback_queue

        self._config = config
        self._running = False

    async def run(self) -> None:
        """Pull jobs from the input queue and process them continuously."""
        self._running = True

        while self._running:
            job: Job | None = None

            try:
                # don't start processing until we have space in the output queue to reduce memory usage
                if self._config.await_output_space and self._output_queue is not None:
                    while self._output_queue.full() and self._running:
                        await asyncio.sleep(0.1)

                if not self._running:
                    break

                job = await self._input_queue.get()

                try:
                    await self._process_job(job)
                finally:
                    self._input_queue.task_done()
            except TimeoutError:
                if job is not None:
                    logger.error("Job timed out: %s", job.id)

                continue
            except CancelledError:
                if job is not None:
                    logger.error("Job cancelled: %s", job.id)

                self._running = False
                break

    async def _process_job(self, job: Job) -> None:
        """Process a job and update the status accordingly.

        Args:
            job: The job to process
        """
        work_start = time.perf_counter_ns()
        await self._send_notification(job, self._work_status, work_start)

        max_attempts = max(self._config.max_retries + 1, 1)

        for attempt in range(max_attempts):
            # Retry loop: exception handling is the control flow here (intentional)
            try:
                next_job: Job | None = await self._do_work(job)

                work_end = time.perf_counter_ns()
                await self._send_notification(job, self._work_status, work_start, work_end)

                if not self._output_queue or not next_job:
                    await self._send_notification(job, JobStatus.COMPLETED)
                else:
                    await self._output_queue.put(next_job)

                await self._send_scheduler_feedback(job, was_rate_limited=False)
                return
            except (NotFoundError, ValueError) as e:  # noqa: PERF203
                # Non-retryable errors: fail immediately
                error_type = type(e).__name__

                logger.error(
                    "Worker %s: Job %s failed with %s: %s - failing immediately",
                    self._id,
                    job.id,
                    error_type,
                    e,
                )
                await self._send_notification(job, JobStatus.FAILED)
                return
            except (
                RateLimitError,
                TimeoutError,
                BadGatewayError,
                asyncio.TimeoutError,
                ClientError,
            ) as e:
                is_terminal = await self._handle_retryable_error(job, e, attempt)

                if is_terminal:
                    return
            except Exception as e:
                # Unknown errors: fail immediately (don't retry bugs)
                logger.error(
                    "Worker %s: Job %s unexpected error: %s",
                    self._id,
                    job.id,
                    e,
                    exc_info=True,
                )
                await self._send_notification(job, JobStatus.FAILED)
                return

    async def _handle_retryable_error(
        self,
        job: Job,
        error: Exception,
        attempt: int,
    ) -> bool:
        """Apply the retry policy for a retryable error.

        Args:
            job: The job being processed
            error: The retryable error raised
            attempt: The zero-based attempt index

        Returns:
            True if the job failed terminally (caller must return)
        """
        if isinstance(error, RateLimitError):
            await self._send_scheduler_feedback(job, was_rate_limited=True)

        max_attempts = max(self._config.max_retries + 1, 1)
        error_label = type(error).__name__

        if attempt == max_attempts - 1:
            logger.error(
                "Worker %s: Job %s failed after %d attempts (%s)",
                self._id,
                job.id,
                max_attempts,
                error_label,
            )
            await self._send_notification(job, JobStatus.FAILED)
            return True

        delay = self._calculate_backoff(attempt)
        logger.error(
            "Worker %s: Job %s encountered error (%s), retrying in %.1fs (retry %d/%d)",
            self._id,
            job.id,
            error_label,
            delay,
            attempt + 1,
            max_attempts - 1,
        )
        await asyncio.sleep(delay)
        return False

    async def _send_scheduler_feedback(self, job: Job, was_rate_limited: bool) -> None:
        if self._scheduler_feedback_queue is None:
            return

        await self._scheduler_feedback_queue.put(
            SchedulerFeedback(
                source=job.source,
                was_rate_limited=was_rate_limited,
                timestamp=time.monotonic(),
            )
        )

    async def _send_notification(
        self, job: Job, status: JobStatus, start_time: int = -1, end_time: int = -1
    ) -> None:
        """Send a notification for the job.

        Args:
            job: The job to send notification for
            status: The status to report
        """
        await self._notification_queue.put(
            NotificationJob(
                id=job.id,
                status=status,
                metadata=job.to_metadata(),
                start_time=start_time,
                end_time=end_time,
            )
        )

    def _calculate_backoff(self, attempt: int) -> float:
        """Calculate exponential backoff with jitter.

        Args:
            attempt: The current attempt number

        Returns:
            float: The calculated backoff in seconds
        """
        max_delay = self._config.base_delay * (2**attempt)
        jitter = random.uniform(0, max_delay) * 0.1 if self._config.jitter else 0  # noqa: S311 - non-crypto jitter for retry backoff, security not required

        return max_delay + jitter

    @abstractmethod
    async def _do_work(self, job: Job) -> Job | None:
        """Do the actual work for a job.

        Args:
            job: The job to process

        Returns:
            Job | None: The next job in the pipeline or None if this is the last step
        """
        pass

    def stop(self) -> None:
        """Stop the worker."""
        self._running = False
