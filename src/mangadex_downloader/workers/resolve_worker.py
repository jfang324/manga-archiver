import time
from asyncio import Queue, Semaphore

from ..enums import JobStatus
from ..integrations.content_providers import MangaDexApiClient
from ..types import ProcessedDownloadResource
from .base import Worker, WorkerConfig
from .jobs import (
    DownloadingJob,
    FetchingResourcesJob,
    Job,
    NotificationJob,
)


class ResolveWorker(Worker):
    """Fetches chapter resource data from MangaDex API and creates download jobs.

    Processes FetchingResourcesJob inputs by querying the MangaDex API for chapter
    download URLs and metadata, then outputs DownloadingJob objects.
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        api_client: MangaDexApiClient,
        semaphore: Semaphore,
    ):
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            api_client: The API client for MangaDex
            semaphore: The semaphore to use for global rate limiting
        """
        super().__init__(worker_id, input_queue, output_queue, config, notification_queue)

        self._api_client = api_client
        self._semaphore = semaphore

    async def _do_work(self, job: FetchingResourcesJob) -> DownloadingJob:
        """Fetch, process resources and enqueue them for downloading.

        Args:
            job: The job to process

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
        ) = (
            job.id,
            job.chapter_id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
        )

        if not chapter_id:
            raise ValueError(f"Invalid FetchingResourcesJob missing chapter_id: {job}")

        resolve_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.FETCHING_RESOURCES, resolve_start)

        async with self._semaphore:
            resources: ProcessedDownloadResource = await self._api_client.get_download_resource(
                job.chapter_id
            )

        resolve_end = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.FETCHING_RESOURCES, resolve_start, resolve_end)

        return DownloadingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            urls=resources["urls"],
        )
