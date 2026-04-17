from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..models import ContentSource
from ..models.output_format import OutputFormat


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
    """

    id: str
    manga_title: str
    chapter_number: float
    chapter_title: str
    output_directory: Path
    output_format: OutputFormat


class JobStatus(Enum):
    """An enum class for the status of a job."""

    QUEUED = "queued"
    FETCHING_RESOURCES = "fetching_resources"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class JobMetadata:
    """Metadata for tracking job progress in the Downloads screen.

    Attributes:
        manga_title (str): The title of the manga
        chapter_id (str): The ID of the chapter
        chapter_number (float): The chapter number
        chapter_title (str): The title of the chapter
        completed_at (float): Unix timestamp when job completed (set only on terminal status). Set to -1 if in progress
    """

    manga_title: str
    chapter_id: str
    chapter_number: float
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
    """Job for fetching chapter resources from a content provider.

    Attributes:
        chapter_id (str): The ID of the chapter to fetch
        source (ContentSource): The content source (provider)
    """

    chapter_id: str
    source: ContentSource


@dataclass
class DownloadingJob(Job):
    """Job for downloading images from URLs.

    Attributes:
        urls (list[str]): List of image URLs to download
        source (ContentSource): The content source (provider)
    """

    urls: list[str]
    source: ContentSource


@dataclass
class MergingJob(Job):
    """Job for merging images into output format.

    Attributes:
        image_data (list[bytes]): List of image bytes to merge
        source (ContentSource): The content source (provider)
    """

    image_data: list[bytes]
    source: ContentSource


@dataclass
class UploadJob(Job):
    """Job for uploading merged files to a cloud storage provider.

    Attributes:
        complete_file_data (bytes): The file bytes to upload
        full_name (str): The full name of the file to upload
        source (ContentSource): The content source (provider)
    """

    complete_file_data: bytes
    full_name: str
    source: ContentSource
