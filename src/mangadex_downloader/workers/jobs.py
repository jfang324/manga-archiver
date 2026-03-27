from dataclasses import dataclass
from enum import Enum


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
    """
    Base class for all jobs
    """

    id: str


@dataclass
class FetchingResourcesJob(Job):
    """
    A job for fetching resources for a chapter
    """

    chapter_id: str
    chapter_title: str
    manga_id: str


@dataclass
class DownloadingJob(Job):
    """
    A job for downloading a chapter
    """

    chapter_id: str
    chapter_title: str
    urls: list[str]


@dataclass
class MergingJob(Job):
    """
    A job for merging all the images for a chapter
    """

    output_path: str
    image_data: list[list[bytes]]
