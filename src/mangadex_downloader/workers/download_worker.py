from asyncio import Queue, Semaphore
from typing import Callable

from ..enums import JobStatus
from ..utils import DownloadClient
from .base import Worker, WorkerConfig
from .jobs import DownloadingJob, Job, MergingJob


class DownloadWorker(Worker):
    """
    Worker class for downloading resources for a chapter
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        on_status_change: Callable[[str, JobStatus], None],
        config: WorkerConfig | None,
        download_client: DownloadClient,
        semaphore: Semaphore,
    ):
        """
        Initialize the worker

        Args:
            id (str): The ID of the worker
            input_queue (Queue[Job]): The input queue for the worker
            output_queue (Queue[Job] | None): The output queue for the worker
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (WorkerConfig): The configuration for the worker
            download_client (DownloadClient): The client for downloading images
            semaphore (Semaphore): The semaphore to use for global rate limiting
        """
        super().__init__(id, input_queue, output_queue, on_status_change, config)

        self._download_client = download_client
        self._semaphore = semaphore

    async def _do_work(self, job: DownloadingJob) -> MergingJob:
        """
        Download the resources from a list of URLs and enqueue them for merging

        Args:
            job (DownloadingJob): The job to process

        Returns:
            MergingJob: The next job in the pipeline

        Raises:
            ValueError: If the job is missing URLs
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

        self._on_status_change(job.id, JobStatus.DOWNLOADING)

        async with self._semaphore:
            image_data: list[bytes] = await self._download_client.download_images(urls)

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
