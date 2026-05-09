from dataclasses import dataclass
from enum import Enum

from ..models import ContentSource
from ..models.app_config import AppConfig


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
        app_config (AppConfig): Output settings for the job
        source (ContentSource): The content source (provider)
        payload_size (int): Size of the latest job payload in bytes
        completed_at (float): Unix timestamp when job completed (set only on terminal status). Set to -1 if in progress
    """

    manga_title: str
    chapter_id: str
    chapter_number: float
    chapter_title: str
    app_config: AppConfig
    source: ContentSource
    payload_size: int = 0
    completed_at: float = -1
