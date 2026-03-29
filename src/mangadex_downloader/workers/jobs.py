from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from ..models.app_config import OutputFormat


class JobStatus(Enum):
    """
    An enum class for the status of a job.
    """

    QUEUED = "queued"
    FETCHING_RESOURCES = "fetching_resources"
    DOWNLOADING = "downloading"
    MERGING = "merging"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Base class for all jobs.

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
    """Job for downloading images from URLs.

    Attributes:
        urls: List of image URLs to download
    """

    urls: list[str]


@dataclass
class MergingJob(Job):
    """Job for merging images into output format.

    Attributes:
        image_data: List of image bytes to merge
    """

    image_data: list[bytes]


@dataclass
class BenchmarkJob(Job):
    """Job for tracking job timing across the pipeline."""
