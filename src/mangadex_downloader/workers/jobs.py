from dataclasses import dataclass
from pathlib import Path

from ..enums import JobStatus, OutputFormat


@dataclass
class Job:
    """Base class for all jobs.

    Attributes:
        id (str): The unique identifier for the job
        manga_title (str): The title of the manga
        chapter_number (str): The chapter number (e.g., "1", "2.5")
        chapter_title (str): The title of the chapter
        output_directory (Path): The directory to save output files
        output_format (OutputFormat): The output format (PDF, CBZ, etc.)
    """

    id: str
    manga_title: str
    chapter_number: str
    chapter_title: str
    output_directory: Path
    output_format: OutputFormat


@dataclass
class JobMetadata:
    """Metadata for tracking job progress in the Downloads screen.

    Attributes:
        manga_title (str): The title of the manga
        chapter_id (str): The ID of the chapter
        chapter_number (str): The chapter number (e.g., "1", "2.5")
        chapter_title (str): The title of the chapter
        completed_at (float): Unix timestamp when job completed (set only on terminal status)
    """

    manga_title: str
    chapter_id: str
    chapter_number: str
    chapter_title: str
    completed_at: float = -1


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
