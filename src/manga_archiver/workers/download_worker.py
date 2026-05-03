import time
from asyncio import Queue

from ..integrations.content_providers import ContentProviderManager
from ..integrations.content_providers.constants import CDN_HEADERS
from ..utils import DownloadClient
from .base import Worker, WorkerConfig
from .jobs import DownloadingJob, Job, JobStatus, MergingJob, NotificationJob


class DownloadWorker(Worker):
    """Downloads images from content provider URLs and prepares them for merging."""

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        download_client: DownloadClient,
        provider_manager: ContentProviderManager,
    ) -> None:
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            download_client: The client for downloading images
            provider_manager: The content provider manager (provides download rate limiting)
        """
        super().__init__(worker_id, input_queue, output_queue, config, notification_queue)

        self._download_client = download_client
        self._provider_manager = provider_manager

    async def _do_work(self, job: Job) -> MergingJob:
        """Download resources from URLs and enqueue them for merging.

        Args:
            job: The job to process

        Returns:
            MergingJob: The next job in the pipeline

        Raises:
            ValueError: If the job is missing URLs
        """
        if not isinstance(job, DownloadingJob):
            raise ValueError(f"Invalid job type: {type(job).__name__}")

        (
            job_id,
            manga_title,
            chapter_title,
            chapter_number,
            app_config,
            urls,
            chapter_id,
            source,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.chapter_number,
            job.app_config,
            job.urls,
            job.chapter_id,
            job.source,
        )

        if not urls:
            raise ValueError(f"Invalid DownloadingJob missing urls: {job}")

        headers = CDN_HEADERS.get(source, {})

        download_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.DOWNLOADING, download_start)

        semaphore = self._provider_manager.get_download_semaphore(source)
        try:
            image_data: list[bytes] = await self._download_client.download_images(
                urls, headers, semaphore
            )
        except Exception as download_error:
            try:
                await self._provider_manager.invalidate_cache(source, chapter_id)
            except Exception:
                raise download_error

            raise

        download_end = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.DOWNLOADING, download_start, download_end)

        return MergingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            app_config=app_config,
            image_data=image_data,
            source=job.source,
        )
