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
        max_retry_attempts = max_attempts - 1

        for attempt in range(max_attempts):
            is_final_attempt = attempt == max_attempts - 1

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
            except NotFoundError:
                # 404: Fail fast, don't retry
                logger.error(
                    "Worker %s: Job %s failed with 404 NotFound - failing immediately",
                    self._id,
                    job.id,
                )
                await self._send_notification(job, JobStatus.FAILED)
                return
            except RateLimitError:
                await self._send_scheduler_feedback(job, was_rate_limited=True)

                # 429: Retry with standard backoff
                if is_final_attempt:
                    logger.error(
                        "Worker %s: Job %s rate limited after %d attempts - failing",
                        self._id,
                        job.id,
                        max_attempts,
                    )
                    await self._send_notification(job, JobStatus.FAILED)
                    return

                delay = self._calculate_backoff(attempt)
                logger.error(
                    "Worker %s: Job %s rate limited, retrying in %.1fs (retry %d/%d)",
                    self._id,
                    job.id,
                    delay,
                    attempt + 1,
                    max_retry_attempts,
                )
                await asyncio.sleep(delay)
            except (TimeoutError, BadGatewayError, asyncio.TimeoutError, ClientError) as e:
                # Transient network errors: retry normally
                if is_final_attempt:
                    logger.error(
                        "Worker %s: Job %s network failed after %d attempts",
                        self._id,
                        job.id,
                        max_attempts,
                    )
                    await self._send_notification(job, JobStatus.FAILED)
                    return

                delay = self._calculate_backoff(attempt)
                logger.error(
                    "Worker %s: Job %s network error: %s, retrying in %.1fs (retry %d/%d)",
                    self._id,
                    job.id,
                    type(e).__name__,
                    delay,
                    attempt + 1,
                    max_retry_attempts,
                )
                await asyncio.sleep(delay)
            except ValueError as e:
                # Data validation errors: don't retry
                logger.error(
                    "Worker %s: Job %s validation error: %s - failing immediately",
                    self._id,
                    job.id,
                    e,
                )
                await self._send_notification(job, JobStatus.FAILED)
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
                manga_title=job.manga_title,
                chapter_number=job.chapter_number,
                chapter_title=job.chapter_title,
                app_config=job.app_config,
                source=job.source,
                status=status,
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
