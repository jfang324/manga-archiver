import asyncio
import logging
import random
from abc import ABC, abstractmethod
from asyncio import CancelledError, Queue
from dataclasses import dataclass
from typing import Callable

from aiohttp import ClientError

from ..enums import JobStatus
from ..integrations.exceptions import (
    NotFoundError,
    RateLimitError,
)
from .jobs import Job

logger = logging.getLogger(__name__)


@dataclass
class WorkerConfig:
    """
    A data container for the configuration of a worker.

    Attributes:
        max_retries (int): The maximum number of retries for failed downloads
        base_delay (int): The base delay in seconds between retries
        jitter (bool): Whether to apply jitter to the delay between retries
        await_output_space (bool): Whether to check the output queue for space before processing.
    """

    max_retries: int = 5
    base_delay: int = 2
    jitter: bool = False
    await_output_space: bool = False


class Worker(ABC):
    """
    The base worker class that all workers will implement
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        on_status_change: Callable[[str, JobStatus], None],
        config: WorkerConfig | None,
    ) -> None:
        """
        Initialize the worker

        Args:
            id (str): The ID of the worker
            input_queue (Queue[Job]): The input queue for the worker
            output_queue (Queue[Job] | None): The output queue for the worker
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (WorkerConfig): The configuration for the worker
        """
        self._id = id
        self._input_queue = input_queue
        self._output_queue = output_queue
        self._on_status_change = on_status_change

        self._config = config or WorkerConfig()
        self._running = False

    async def run(self) -> None:
        """
        Main loop - continuously pull jobs from the input queue and process them.
        """
        self._running = True

        while self._running:
            job: Job | None = None

            try:
                if self._config.await_output_space and self._output_queue:
                    while self._output_queue.full():
                        await asyncio.sleep(0.1)

                job = await self._input_queue.get()

                await self._process_job(job)

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

    async def _process_job(self, job: Job, attempt: int = 0) -> None:
        """
        Process a job and update the status accordingly.

        Args:
            job (Job): The job to process
            attempt (int): The current attempt number for retries
        """
        try:
            next_job: Job | None = await self._do_work(job)

            if not self._output_queue or not next_job:
                self._on_status_change(job.id, JobStatus.COMPLETED)
                return

            await self._output_queue.put(next_job)
        except NotFoundError:
            # 404: Fail fast, don't retry
            logger.error(
                "Worker %s: Job %s failed with 404 NotFound - failing immediately",
                self._id,
                job.id,
            )
            self._on_status_change(job.id, JobStatus.FAILED)
            return
        except RateLimitError:
            # 429: Retry with standard backoff
            if attempt < self._config.max_retries:
                delay = self._calculate_backoff(attempt)
                logger.error(
                    "Worker %s: Job %s rate limited, retrying in %.1fs (attempt %d/%d)",
                    self._id,
                    job.id,
                    delay,
                    attempt + 1,
                    self._config.max_retries,
                )
                await asyncio.sleep(delay)
                await self._process_job(job, attempt + 1)
                return
            logger.error(
                "Worker %s: Job %s rate limited after %d attempts - failing",
                self._id,
                job.id,
                self._config.max_retries,
            )
            self._on_status_change(job.id, JobStatus.FAILED)
            return
        except (asyncio.TimeoutError, ClientError) as e:
            # Transient network errors: retry normally
            if attempt < self._config.max_retries:
                delay = self._calculate_backoff(attempt)
                logger.error(
                    "Worker %s: Job %s network error: %s, retrying in %.1fs (attempt %d/%d)",
                    self._id,
                    job.id,
                    type(e).__name__,
                    delay,
                    attempt + 1,
                    self._config.max_retries,
                )
                await asyncio.sleep(delay)
                await self._process_job(job, attempt + 1)
                return
            logger.error(
                "Worker %s: Job %s network failed after %d attempts",
                self._id,
                job.id,
                self._config.max_retries,
            )
            self._on_status_change(job.id, JobStatus.FAILED)
            return
        except (ValueError, IndexError, AttributeError) as e:
            # Data validation errors: don't retry
            logger.error(
                "Worker %s: Job %s validation error: %s - failing immediately",
                self._id,
                job.id,
                e,
            )
            self._on_status_change(job.id, JobStatus.FAILED)
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
            self._on_status_change(job.id, JobStatus.FAILED)
            return

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter.

        Args:
            attempt (int): The current attempt number

        Returns:
            float: The calculated backoff in seconds
        """
        max_delay = self._config.base_delay * (2**attempt)
        jitter = random.uniform(0, max_delay) * 0.1 if self._config.jitter else 0

        return max_delay + jitter

    @abstractmethod
    async def _do_work(self, job: Job) -> Job | None:
        """
        Do the actual work for a job.

        Args:
            job (Job): The job to process

        Returns:
            Job | None: The next job in the pipeline or None if this is the last step
        """
        pass

    def stop(self) -> None:
        """
        Stop the worker.
        """
        self._running = False
