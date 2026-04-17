import time
from asyncio import Queue

from ..utils import MultiFormatExporter
from ..workers.jobs import JobStatus
from .base import Worker, WorkerConfig
from .jobs import (
    Job,
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
    ):
        """Initialize the worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            multi_format_exporter: The exporter to use for merging
        """
        super().__init__(worker_id, input_queue, output_queue, config, notification_queue)

        self._multi_format_exporter = multi_format_exporter

    async def _do_work(self, job: MergingJob) -> Job:
        """Merge the downloaded images into a single PDF or CBZ.

        Args:
            job: The merging job containing image data to process

        Returns:
            UploadJob: The output job containing the related data, complete_file_data will be empty if output_queue is None
        """
        (
            job_id,
            manga_title,
            output_directory,
            output_format,
            image_data,
            chapter_number,
            chapter_title,
        ) = (
            job.id,
            job.manga_title,
            job.output_directory,
            job.output_format,
            job.image_data,
            job.chapter_number,
            job.chapter_title or "untitled",
        )

        if not isinstance(chapter_number, float):
            raise ValueError("chapter_number must be a float")

        chapter_title = chapter_title.rstrip()

        output_name: str = f"{manga_title} [{chapter_number:g}] - {chapter_title}"

        if image_data is None:
            raise ValueError("image_data must not be None for merging")
        if output_directory is None:
            raise ValueError("output_directory must not be None for merging")
        if output_format is None:
            raise ValueError("output_format must not be None for merging")

        merge_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.MERGING, merge_start)

        full_name, file_data = self._multi_format_exporter.generate(
            image_data_list=image_data,
            output_directory=output_directory,
            output_name=output_name,
            output_format=output_format,
            return_bytes=self._output_queue is not None,
        )

        merge_end = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.MERGING, merge_start, merge_end)

        return UploadJob(
            id=job_id,
            manga_title=manga_title,
            chapter_number=chapter_number,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            complete_file_data=file_data,
            full_name=full_name,
            source=job.source,
        )
