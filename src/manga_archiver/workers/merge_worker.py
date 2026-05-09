import asyncio
from asyncio import Queue

from ..models.app_config import AppConfig
from ..utils import MultiFormatExporter
from .base import Worker, WorkerConfig
from .jobs import (
    Job,
    JobStatus,
    MergingJob,
    NotificationJob,
    UploadJob,
)


class MergeWorker(Worker):
    """Worker class for merging the downloaded images into a single PDF or CBZ."""

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        multi_format_exporter: MultiFormatExporter,
    ) -> None:
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            multi_format_exporter: The exporter to use for merging
        """
        super().__init__(
            worker_id, input_queue, output_queue, config, notification_queue, JobStatus.MERGING
        )

        self._multi_format_exporter = multi_format_exporter

    async def _do_work(self, job: Job) -> Job:
        """Merge the downloaded images into a single PDF or CBZ.

        Args:
            job: The merging job containing image data to process

        Returns:
            UploadJob: The output job containing the related data, complete_file_data will be empty if output_queue is None
        """
        if not isinstance(job, MergingJob):
            raise ValueError(f"Invalid job type: {type(job).__name__}")

        (
            job_id,
            manga_title,
            app_config,
            image_data,
            chapter_number,
            chapter_title,
        ) = (
            job.id,
            job.manga_title,
            job.app_config,
            job.image_data,
            job.chapter_number,
            job.chapter_title,
        )

        if not isinstance(chapter_number, float):
            raise ValueError("chapter_number must be a float")

        chapter_title = chapter_title.rstrip()

        output_name: str = f"{manga_title} [{chapter_number:g}] - {chapter_title}"

        if image_data is None:
            raise ValueError("image_data must not be None for merging")
        if not isinstance(app_config, AppConfig):
            raise ValueError("app_config must be an AppConfig instance")

        # need to delegate to thread pools to avoid blocking the event loop
        full_name, file_data = await asyncio.to_thread(
            self._multi_format_exporter.generate,
            image_data_list=image_data,
            output_directory=app_config.output_path,
            output_name=output_name,
            output_format=app_config.output_format,
            return_bytes=self._output_queue is not None,
            quality=app_config.quality,
            optimize=app_config.optimize,
        )

        return UploadJob(
            id=job_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            app_config=app_config,
            complete_file_data=file_data,
            full_name=full_name,
            source=job.source,
            payload_size=len(file_data),
        )
