from asyncio import Queue, Semaphore
from typing import TYPE_CHECKING

from ..enums import JobStatus
from ..integrations import MangaDexApiClient
from .base import Worker, WorkerConfig
from .jobs import (
    DownloadingJob,
    FetchingResourcesJob,
    Job,
    NotificationJob,
)

if TYPE_CHECKING:
    from ..types import ProcessedDownloadResource

import time


class ResolveWorker(Worker):
    """
    Worker class for fetching and processing resources for a chapter
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig | None,
        api_client: MangaDexApiClient,
        semaphore: Semaphore,
    ):
        """
        Initialize the worker

        Args:
            id (str): The ID of the worker
            input_queue (Queue[Job]): The input queue for the worker
            output_queue (Queue[Job] | None): The output queue for the worker
            notification_queue (Queue[NotificationJob]): The queue for notification jobs
            config (WorkerConfig): The configuration for the worker
            api_client (MangaDexApiClient): The API client for MangaDex
            semaphore (Semaphore): The semaphore to use for global rate limiting
        """
        super().__init__(id, input_queue, output_queue, config, notification_queue)

        self._api_client = api_client
        self._semaphore = semaphore

    async def _do_work(self, job: FetchingResourcesJob) -> DownloadingJob:
        """
        Fetch the resources process them and enqueue them for downloading

        Args:
            job (FetchingResourcesJob): The job to process

        Returns:
            DownloadingJob: The next job in the pipeline

        Raises:
            ValueError: If the job is missing a chapter ID
        """
        (
            job_id,
            chapter_id,
            manga_title,
            chapter_title,
            output_directory,
            output_format,
            start_time,
            end_time,
        ) = (
            job.id,
            job.chapter_id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
            job.start_time,
            job.end_time,
        )

        if not chapter_id:
            raise ValueError(f"Invalid FetchingResourcesJob missing chapter_id: {job}")

        await self._notification_queue.put(
            NotificationJob(
                id=job_id,
                manga_title=manga_title,
                chapter_title=chapter_title,
                output_directory=output_directory,
                output_format=output_format,
                start_time=start_time,
                end_time=end_time,
                status=JobStatus.FETCHING_RESOURCES,
            )
        )

        start_time = time.perf_counter_ns()

        async with self._semaphore:
            resources: ProcessedDownloadResource = (
                await self._api_client.get_download_resource(job.chapter_id)
            )

        return DownloadingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            urls=resources["urls"],
            start_time=start_time,
            end_time=end_time,
        )
