import asyncio
import logging
from asyncio import Queue
from typing import Callable

from ..enums import JobStatus
from .jobs import JobMetadata, NotificationJob

logger = logging.getLogger(__name__)


class NotificationWorker:
    """
    Worker that tracks job statuses and updates the PipelineManager's job status dict.

    Attributes:
        on_status_update: Callback to update job status in PipelineManager
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue,
        on_status_update: Callable[[str, JobStatus, JobMetadata], None],
    ) -> None:
        """
        Initialize the notification worker.

        Args:
            id: The ID of the worker
            input_queue: The queue to receive notification jobs from
            on_status_update: Callback to update job status in PipelineManager
        """
        self._id = id
        self._input_queue = input_queue
        self._on_status_update = on_status_update
        self._running = False

    async def run(self) -> None:
        self._running = True

        while self._running:
            try:
                job: NotificationJob = await self._input_queue.get()
                await self._do_work(job)
                self._input_queue.task_done()
            except asyncio.CancelledError:
                self._running = False
                break

    async def _do_work(self, job: NotificationJob) -> None:
        metadata = JobMetadata(
            chapter_id=job.id,
            manga_title=job.manga_title,
            chapter_title=job.chapter_title,
            start_time=job.start_time,
            end_time=job.end_time,
        )
        self._on_status_update(job.id, job.status, metadata)

    def stop(self) -> None:
        self._running = False
