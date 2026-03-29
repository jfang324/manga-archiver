import time

from ..utils.multi_format_exporter import MultiFormatExporter
from .base import Worker
from .jobs import BenchmarkJob, JobStatus, MergingJob


class MergeWorker(Worker):
    """
    Worker class for merging the downloaded images into a single PDF or CBZ

    Attributes:
        pdf_generator (MultiFormatExporter): The exporter to use for merging
    """

    def __init__(self, pdf_generator: MultiFormatExporter, **kwargs):
        """
        Initialize the worker

        Args:
            pdf_generator (MultiFormatExporter): The exporter to use for merging
        """
        super().__init__(**kwargs)

        self.pdf_generator = pdf_generator

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

        self.on_status_change(job.id, JobStatus.MERGING)

        chapter_number, chapter_title = chapter_title.split(" ", 1)
        chapter_number = chapter_number.rstrip(".")

        output_name: str = f"{manga_title} [{chapter_number}] - {chapter_title}"

        self.pdf_generator.generate(
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
