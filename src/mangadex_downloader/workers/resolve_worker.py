from asyncio import Semaphore
from typing import TYPE_CHECKING

from ..integrations.mangadex import MangaDexApiClient
from .base import Worker
from .jobs import DownloadingJob, FetchingResourcesJob, JobStatus

if TYPE_CHECKING:
    from ..types import ProcessedDownloadResource


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
        job_id, chapter_id, chapter_title = (job.id, job.chapter_id, job.chapter_title)

        if not chapter_id:
            raise ValueError(f"Invalid FetchingResourcesJob missing chapter_id: {job}")

        self.on_status_change(job.id, JobStatus.FETCHING_RESOURCES)

        async with self._semaphore:
            resources: ProcessedDownloadResource = (
                await self.api_client.get_download_resource(job.chapter_id)
            )

        return DownloadingJob(
            id=job_id,
            chapter_id=chapter_id,
            chapter_title=chapter_title,
            urls=resources["urls"],
        )
