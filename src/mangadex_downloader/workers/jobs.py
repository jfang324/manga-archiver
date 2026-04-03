from dataclasses import dataclass
from pathlib import Path

from ..enums import JobStatus, OutputFormat


@dataclass
class Job:
    """Base class for all jobs.

    Attributes:
        id (str): The unique identifier for the job
        manga_title (str): The title of the manga
        chapter_title (str): The title of the chapter
        output_directory (Path): The directory to save output files
        output_format (OutputFormat): The output format (PDF, CBZ, etc.)
        start_time (float): The start time in nanoseconds (-1 if not started)
        end_time (float): The end time in nanoseconds (-1 if not completed)
    """

    id: str
    manga_title: str
    chapter_title: str
    output_directory: Path
    output_format: OutputFormat
    start_time: float
    end_time: float


@dataclass
class JobMetadata:
    """Metadata for tracking job progress in the Downloads screen.

    Attributes:
        manga_title (str): The title of the manga
        chapter_id (str): The ID of the chapter
        chapter_title (str): The title of the chapter
        start_time (float): The start time in nanoseconds (-1 if not started)
        end_time (float): The end time in nanoseconds (-1 if not completed)
    """

    manga_title: str
    chapter_id: str
    chapter_title: str
    start_time: float  # initialized to -1 on enqueue, workers set to time.perf_counter_ns() on start
    end_time: float  # initialized to -1 on enqueue, workers set to time.perf_counter_ns() on end


@dataclass
class NotificationJob(Job):
    """Job for notifying status changes in the pipeline.

    Attributes:
        status (JobStatus): The status of the job
    """

    status: JobStatus


@dataclass
class FetchingResourcesJob(Job):
    """Job for fetching chapter resources from MangaDex API.

    Attributes:
        chapter_id (str): The ID of the chapter to fetch
    """

    chapter_id: str


@dataclass
class DownloadingJob(Job):
    """Job for downloading images from URLs.

    Attributes:
        urls (list[str]): List of image URLs to download
    """

    urls: list[str]


@dataclass
class MergingJob(Job):
    """Job for merging images into output format.

    Attributes:
        image_data (list[bytes]): List of image bytes to merge
    """

    image_data: list[bytes]


@dataclass
class UploadJob(Job):
    """Job for uploading merged files to a cloud storage provider.

    Attributes:
        complete_file_data (bytes): The file bytes to upload
        full_name (str): The full name of the file to upload
    """

    complete_file_data: bytes
    full_name: str


@dataclass
class BenchmarkJob(Job):
    """Job for tracking job timing across the pipeline."""
