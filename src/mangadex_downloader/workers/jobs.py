from dataclasses import dataclass
from pathlib import Path

from ..enums import JobStatus, OutputFormat


@dataclass
class Job:
    """
    Base class for all jobs.

    Attributes:
        id: The unique identifier for the job
        manga_title: The title of the manga
        chapter_title: The title of the chapter
        output_directory: The directory to save the output file
        output_format: The output format (PDF, CBZ, etc.)
        start_time: The start time in nanoseconds (-1 if not started)
        end_time: The end time in nanoseconds (-1 if not completed)
    """

    id: str
    manga_title: str
    chapter_title: str
    output_directory: Path
    output_format: OutputFormat
    start_time: float
    end_time: float


@dataclass
class FetchingResourcesJob(Job):
    """Job for fetching chapter resources from MangaDex API.

    Attributes:
        chapter_id: The ID of the chapter to fetch
    """

    chapter_id: str


@dataclass
class DownloadingJob(Job):
    """
    Job for downloading images from URLs.

    Attributes:
        urls: List of image URLs to download
    """

    urls: list[str]


@dataclass
class MergingJob(Job):
    """
    Job for merging images into output format.

    Attributes:
        image_data: List of image bytes to merge
    """

    image_data: list[bytes]


@dataclass
class BenchmarkJob(Job):
    """Job for tracking job timing across the pipeline."""


@dataclass
class JobMetadata:
    """Metadata for tracking job progress in the Downloads screen."""

    chapter_id: str
    manga_title: str
    chapter_title: str
    start_time: float  # initialized to -1 on enqueue, workers set to time.perf_counter_ns() on start
    end_time: float  # initialized to -1 on enqueue, workers set to time.perf_counter_ns() on end


@dataclass
class NotificationJob(Job):
    """Job for notifying status changes in the pipeline."""

    status: JobStatus


@dataclass
class UploadJob(Job):
    """Job for uploading merged files to a cloud storage provider."""

    complete_file_data: list[bytes]
    full_name: str
