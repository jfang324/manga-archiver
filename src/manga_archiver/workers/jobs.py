from dataclasses import dataclass
from pathlib import Path

from ..models import ContentSource
from ..models.output_format import OutputFormat
from .types import JobStatus


@dataclass
class Job:
    """Base class for all jobs.

    Attributes:
        id (str): The unique identifier for the job
        manga_title (str): The title of the manga
        chapter_number (float): The chapter number
        chapter_title (str): The title of the chapter
        output_directory (Path): The directory to save output files
        output_format (OutputFormat): The output format (PDF, CBZ, etc.)
        source (ContentSource): The content source (provider)
    """

    id: str
    manga_title: str
    chapter_number: float
    chapter_title: str
    output_directory: Path
    output_format: OutputFormat
    source: ContentSource


@dataclass
class NotificationJob(Job):
    """Job for notifying status changes in the pipeline.

    Attributes:
        status (JobStatus): The status of the job
        start_time (float): Start time of phase in nanoseconds (-1 if not started)
        end_time (float): End time of phase in nanoseconds (-1 if not completed)
    """

    status: JobStatus
    start_time: float = -1
    end_time: float = -1


@dataclass
class FetchingResourcesJob(Job):
    """Job for fetching chapter resources from a content provider.

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
