import time
from asyncio import Queue
from typing import Callable

from ..enums import JobStatus
from ..utils import MultiFormatExporter
from .base import Worker, WorkerConfig
from .jobs import BenchmarkJob, Job, MergingJob


class MergeWorker(Worker):
    """
    Worker class for merging the downloaded images into a single PDF or CBZ
    """

    def __init__(
        self,
        id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        on_status_change: Callable[[str, JobStatus], None],
        config: WorkerConfig | None,
        multi_format_exporter: MultiFormatExporter,
    ):
        """
        Initialize the worker

        Args:
            id (str): The ID of the worker
            input_queue (Queue[Job]): The input queue for the worker
            output_queue (Queue[Job] | None): The output queue for the worker
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (WorkerConfig): The configuration for the worker
            pdf_generator (MultiFormatExporter): The exporter to use for merging
        """
        super().__init__(id, input_queue, output_queue, on_status_change, config)

        self._multi_format_exporter = multi_format_exporter

    async def _do_work(self, job: MergingJob) -> BenchmarkJob:
        """
        Merge the downloaded images into a single PDF

        Args:
            job (MergingJob): The job to process
        """
        (
            job_id,
            manga_title,
            chapter_title,
            output_directory,
            output_format,
            image_data,
            start_time,
            _,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
            job.image_data,
            job.start_time,
            job.end_time,
        )

        self._on_status_change(job.id, JobStatus.MERGING)

        chapter_number, chapter_title = chapter_title.split(" ", 1)
        chapter_number = chapter_number.rstrip(".")

        output_name: str = f"{manga_title} [{chapter_number}] - {chapter_title}"

        self._multi_format_exporter.generate(
            image_data_list=image_data,
            output_directory=output_directory,
            output_name=output_name,
            output_format=output_format,
        )
        end_time = time.perf_counter_ns()

        return BenchmarkJob(
            id=job_id,
            manga_title=manga_title,
            chapter_title=chapter_title,
            output_directory=output_directory,
            output_format=output_format,
            start_time=start_time,
            end_time=end_time,
        )
