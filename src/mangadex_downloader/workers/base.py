import asyncio
import logging
import random
from abc import ABC, abstractmethod
from asyncio import CancelledError, Queue, TimeoutError
from dataclasses import dataclass
from typing import Callable

from ..enums import JobStatus
from .jobs import Job


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
                    logging.error(f"Job timed out: {job.id}")

                continue
            except CancelledError:
                if job is not None:
                    logging.error(f"Job cancelled: {job.id}")

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
        except Exception as e:
            if attempt < self._config.max_retries:
                delay = self._calculate_backoff(attempt)

                await asyncio.sleep(delay)
                await self._process_job(job, attempt + 1)
            else:
                logging.error(
                    f"Worker {self._id} failed: {job.id} after {attempt} attempts with error: {e}"
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
