from dataclasses import dataclass
from enum import Enum


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
