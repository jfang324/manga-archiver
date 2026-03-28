from asyncio import Semaphore
from typing import TYPE_CHECKING

from ..integrations.mangadex import MangaDexApiClient
from .base import Worker
from .jobs import DownloadingJob, FetchingResourcesJob, JobStatus

if TYPE_CHECKING:
    from ..types import ProcessedDownloadResource

import time


class ResolveWorker(Worker):
    """
    Worker class for fetching and processing resources for a chapter

    Attributes:
        api_client (MangaDexApiClient): The API client for MangaDex
    """

    def __init__(self, api_client: MangaDexApiClient, semaphore: Semaphore, **kwargs):
        """
        Initialize the worker

        Args:
            api_client (MangaDexApiClient): The API client for MangaDex
            semaphore (Semaphore): The semaphore to use for global rate limiting
        """
        super().__init__(**kwargs)

        self.api_client = api_client
        self._semaphore = semaphore

    async def _do_work(self, job: FetchingResourcesJob) -> DownloadingJob:
        """
        Fetch the resources process them and enqueue them for downloading

        Args:
            job (FetchingResourcesJob): The job to process

        Returns:
            DownloadingJob: The next job in the pipeline
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

        self.on_status_change(job.id, JobStatus.FETCHING_RESOURCES)

        start_time = time.perf_counter_ns()

        async with self._semaphore:
            resources: ProcessedDownloadResource = (
                await self.api_client.get_download_resource(job.chapter_id)
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
