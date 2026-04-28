import time
from asyncio import Queue

from ..integrations.content_providers import ContentProviderManager
from ..models import DownloadResource
from .base import Worker, WorkerConfig
from .jobs import (
    DownloadingJob,
    FetchingResourcesJob,
    Job,
    JobStatus,
    NotificationJob,
)
from .scheduler import SchedulerFeedback


class ResolveWorker(Worker):
    """Fetches chapter resources from content providers and creates download jobs.

    Processes FetchingResourcesJob inputs by querying the provider manager for
    chapter download URLs and metadata, then outputs DownloadingJob objects.
    """

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        provider_manager: ContentProviderManager,
        scheduler_feedback_queue: Queue[SchedulerFeedback] | None = None,
    ) -> None:
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            provider_manager: The content provider manager (handles rate limiting internally)
            scheduler_feedback_queue: Optional queue for scheduler result feedback
        """
        super().__init__(
            worker_id,
            input_queue,
            output_queue,
            config,
            notification_queue,
            scheduler_feedback_queue,
        )

        self._provider_manager = provider_manager

    async def _do_work(self, job: Job) -> DownloadingJob:
        """Fetch, process resources and enqueue them for downloading.

        Args:
            job: The job to process

        Returns:
            DownloadingJob: The next job in the pipeline

        Raises:
            ValueError: If the job is missing a chapter ID
        """
        if not isinstance(job, FetchingResourcesJob):
            raise ValueError(f"Invalid job type: {type(job).__name__}")

        (
            job_id,
            chapter_id,
            manga_title,
            chapter_title,
            chapter_number,
            output_directory,
            output_format,
        ) = (
            job.id,
            job.chapter_id,
            job.manga_title,
            job.chapter_title,
            job.chapter_number,
            job.output_directory,
            job.output_format,
        )

        if not chapter_id:
            raise ValueError(f"Invalid FetchingResourcesJob missing chapter_id: {job}")

        resolve_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.FETCHING_RESOURCES, resolve_start)

        resources: DownloadResource = await self._provider_manager.get_download_resource(
            job.source, job.chapter_id
        )

        resolve_end = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.FETCHING_RESOURCES, resolve_start, resolve_end)

        return DownloadingJob(
            id=job_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            urls=resources.urls,
            source=job.source,
        )
