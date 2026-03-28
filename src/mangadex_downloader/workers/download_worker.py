from asyncio import Semaphore

from ..utils.downloader import DownloadClient
from .base import Worker
from .jobs import DownloadingJob, JobStatus, MergingJob


class DownloadWorker(Worker):
    """
    Worker class for downloading resources for a chapter

    Attributes:
        download_client (DownloadClient): The client for downloading images
    """

    def __init__(self, download_client: DownloadClient, semaphore: Semaphore, **kwargs):
        """
        Initialize the worker

        Args:
            download_client (DownloadClient): The client for downloading images
            semaphore (Semaphore): The semaphore to use for global rate limiting
        """
        super().__init__(**kwargs)

        self.download_client = download_client
        self._semaphore = semaphore

    async def _do_work(self, job: DownloadingJob) -> MergingJob:
        """
        Download the resources and merge them into a single PDF

        Args:
            job (DownloadingJob): The job to process

        Returns:
            MergingJob: The next job in the pipeline
        """
        (
            job_id,
            manga_title,
            chapter_title,
            output_directory,
            output_format,
            urls,
            start_time,
            end_time,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
            job.urls,
            job.start_time,
            job.end_time,
        )

        if not urls:
            raise ValueError(f"Invalid DownloadingJob missing urls: {job}")

        self.on_status_change(job.id, JobStatus.DOWNLOADING)

        async with self._semaphore:
            image_data: list[bytes] = await self.download_client.download_images(urls)

        return MergingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            image_data=image_data,
            start_time=start_time,
            end_time=end_time,
        )
