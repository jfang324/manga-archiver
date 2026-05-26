from dataclasses import dataclass, field

from ..models import ContentSource
from ..models.app_config import AppConfig
from .types import JobMetadata, JobStatus


@dataclass(frozen=True)
class Job:
    """Base class for all jobs.

    Attributes:
        id (str): The unique identifier for the job
        manga_title (str): The title of the manga
        chapter_number (float): The chapter number
        chapter_title (str): The title of the chapter
        app_config (AppConfig): Output settings for this job
        source (ContentSource): The content source (provider)
        payload_size (int): Byte size of the in-memory job payload
    """

    id: str
    manga_title: str
    chapter_number: float
    chapter_title: str
    app_config: AppConfig
    source: ContentSource
    payload_size: int = field(default=0, kw_only=True)

    def to_metadata(self) -> JobMetadata:
        """Create a lightweight metadata snapshot for status notifications."""
        return JobMetadata(
            chapter_id=self.id,
            manga_title=self.manga_title,
            chapter_number=self.chapter_number,
            chapter_title=self.chapter_title,
            app_config=self.app_config,
            source=self.source,
            payload_size=self.payload_size,
        )


@dataclass
class NotificationJob:
    """Job for notifying status changes in the pipeline.

    Attributes:
        id (str): The unique identifier for the job
        status (JobStatus): The status of the job
        metadata (JobMetadata): Lightweight status metadata snapshot
        start_time (float): Start time of phase in nanoseconds (-1 if not started)
        end_time (float): End time of phase in nanoseconds (-1 if not completed)
    """

    id: str
    status: JobStatus
    metadata: JobMetadata
    start_time: float = -1
    end_time: float = -1


@dataclass(frozen=True)
class FetchingResourcesJob(Job):
    """Job for fetching chapter resources from a content provider.

    Attributes:
        chapter_id (str): The ID of the chapter to fetch
    """

    chapter_id: str


@dataclass(frozen=True)
class DownloadingJob(Job):
    """Job for downloading images from URLs.

    Attributes:
        urls (list[str]): List of image URLs to download
        chapter_id (str): The chapter ID used for cache invalidation
    """

    urls: list[str]
    chapter_id: str


@dataclass(frozen=True)
class MergingJob(Job):
    """Job for merging images into output format.

    Attributes:
        image_data (list[bytes]): List of image bytes to merge
    """

    image_data: list[bytes]


@dataclass(frozen=True)
class UploadJob(Job):
    """Job for uploading merged files to a cloud storage provider.

    Attributes:
        complete_file_data (bytes): The file bytes to upload
        full_name (str): The full name of the file to upload
    """

    complete_file_data: bytes
    full_name: str
