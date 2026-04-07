import time
from asyncio import Queue

from ..enums import JobStatus
from ..utils import MultiFormatExporter
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
        id: str,  # noqa: A002
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        multi_format_exporter: MultiFormatExporter,
    ):
        """Initialize the worker.

        Args:
            id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            multi_format_exporter: The exporter to use for merging
        """
        super().__init__(id, input_queue, output_queue, config, notification_queue)

        self._multi_format_exporter = multi_format_exporter

    async def _do_work(self, job: MergingJob) -> Job:
        """Merge the downloaded images into a single PDF or CBZ.

        Args:
            job: The merging job containing image data to process

        Returns:
            UploadJob for archive mode, or None if no output queue configured
        """
        (
            job_id,
            manga_title,
            chapter_title,
            output_directory,
            output_format,
            image_data,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
            job.image_data,
        )

        try:
            chapter_number, stripped_title = chapter_title.split(" ", 1)
        except ValueError as e:
            raise ValueError(
                f"Malformed chapter_title format (expected '<num> <title>'): '{chapter_title}'"
            ) from e

        chapter_number = chapter_number.rstrip(".")
        stripped_title = stripped_title.rstrip(".")

        output_name: str = f"{manga_title} [{chapter_number}] - {stripped_title}"

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
            chapter_title=stripped_title,
            output_directory=output_directory,
            output_format=output_format,
            complete_file_data=file_data,
            full_name=full_name,
        )
