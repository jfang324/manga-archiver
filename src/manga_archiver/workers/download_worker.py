import time
from asyncio import Queue, Semaphore

from ..integrations.content_providers.header_mappings import CDN_HEADERS
from ..utils import DownloadClient
from ..workers.jobs import JobStatus
from .base import Worker, WorkerConfig
from .jobs import DownloadingJob, Job, MergingJob, NotificationJob


class DownloadWorker(Worker):
    """Downloads images from content provider URLs and prepares them for merging.

    Uses an async download client and semaphore-based rate limiting to fetch
    images for a chapter from provider URLs.
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        download_client: DownloadClient,
        semaphore: Semaphore,
    ):
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            download_client: The client for downloading images
            semaphore: The semaphore to use for global rate limiting
        """
        super().__init__(worker_id, input_queue, output_queue, config, notification_queue)

        self._download_client = download_client
        self._semaphore = semaphore

    async def _do_work(self, job: DownloadingJob) -> MergingJob:
        """Download resources from URLs and enqueue them for merging.

        Args:
            job: The job to process

        Returns:
            MergingJob: The next job in the pipeline

        Raises:
            ValueError: If the job is missing URLs
        """
        (
            job_id,
            manga_title,
            chapter_title,
            chapter_number,
            output_directory,
            output_format,
            urls,
            source,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.chapter_number,
            job.output_directory,
            job.output_format,
            job.urls,
            job.source,
        )

        if not urls:
            raise ValueError(f"Invalid DownloadingJob missing urls: {job}")

        headers = CDN_HEADERS.get(source, {})

        download_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.DOWNLOADING, download_start)

        async with self._semaphore:
            image_data: list[bytes] = await self._download_client.download_images(urls, headers)

        download_end = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.DOWNLOADING, download_start, download_end)

        return MergingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            image_data=image_data,
            source=job.source,
        )
