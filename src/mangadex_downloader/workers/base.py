import asyncio
import logging
import random
from abc import ABC, abstractmethod
from asyncio import CancelledError, Queue, TimeoutError
from dataclasses import dataclass
from typing import Callable

from .jobs import Job, JobStatus


@dataclass
class WorkerConfig:
    """
    A data container for the configuration of a worker.

    Attributes:
        max_retries (int): The maximum number of retries for failed downloads.
        base_delay (int): The base delay in seconds between retries.
        jitter (bool): Whether to apply jitter to the delay between retries.
        await_output_space (bool): Whether to check the output queue for space before processing.
    """

    max_retries: int = 5
    base_delay: int = 2
    jitter: bool = False
    await_output_space: bool = False


class Worker(ABC):
    """
    The base worker class that all workers will implement

    Attributes:
        worker_id (str): The ID of the worker
        input_queue (Queue): The input queue for the worker
        output_queue (Queue | None): The output queue for the worker
        on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
        config (WorkerConfig): The configuration for the worker
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue,
        output_queue: Queue | None,
        on_status_change: Callable[[str, JobStatus], None],
        config: WorkerConfig | None,
    ) -> None:
        """
        Initialize the worker

        Args:
            worker_id (str): The ID of the worker
            input_queue (Queue): The input queue for the worker
            output_queue (Queue | None): The output queue for the worker
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (WorkerConfig): The configuration for the worker
        """
        self.worker_id = worker_id
        self.input_queue = input_queue
        self.output_queue = output_queue
        self.on_status_change = on_status_change

        self.config = config or WorkerConfig()
        self._running = False

    async def run(self) -> None:
        """
        Main loop - continuously pull jobs from the input queue and process them.
        """
        self._running = True

        while self._running:
            job = None
            try:
                if self.config.await_output_space and self.output_queue:
                    while self.output_queue.full():
                        await asyncio.sleep(0.1)

                job = await self.input_queue.get()

                await self._process_job(job)

                self.input_queue.task_done()
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
        """
        try:
            next_job: Job | None = await self._do_work(job)

            if not self.output_queue or not next_job:
                self.on_status_change(job.id, JobStatus.COMPLETED)
                return

            await self.output_queue.put(next_job)
        except Exception:
            if attempt < self.config.max_retries:
                delay = self._calculate_backoff(attempt)

                await asyncio.sleep(delay)
                await self._process_job(job, attempt + 1)
            else:
                # probably put in DL queue
                self.on_status_change(job.id, JobStatus.FAILED)
                return

    def _calculate_backoff(self, attempt: int) -> float:
        """
        Calculate exponential backoff with jitter.

        Args:
            attempt (int): The current attempt number

        Returns:
            float: The calculated backoff in seconds
        """
        max_delay = self.config.base_delay * (2**attempt)
        jitter = random.uniform(0, max_delay) * 0.1 if self.config.jitter else 0

        return max_delay + jitter

    @abstractmethod
    async def _do_work(self, job: Job) -> Job | None:
        """
        Do the actual work for a job.

        Args:
            job (Job): The job to process

        Returns:
            Job | None: The next job in the pipeline
        """
        pass

    def stop(self) -> None:
        """
        Stop the worker.
        """
        self._running = False
