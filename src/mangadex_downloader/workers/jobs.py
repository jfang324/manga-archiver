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
    """
    Base class for all jobs

    Attributes:
        id (str): The ID of the job
        manga_title (str): The title of the manga
        chapter_title (str): The title of the chapter
        output_directory (str): The directory to output the chapter to
        output_format (OutputFormat): The output format of the PDF file
        start_time (int): The start time of the job in nanoseconds initialised at job creation
        end_time (int): The end time of the job in nanoseconds initialised at job creation to -1
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
    """
    A job for fetching resources for a chapter

    Attributes:
        chapter_id (str): The ID of the chapter
    """

    chapter_id: str


@dataclass
class DownloadingJob(Job):
    """
    A job for downloading a chapter

    Attributes:
        urls (list[str]): The URLs of the images to download
    """

    urls: list[str]


@dataclass
class MergingJob(Job):
    """
    A job for merging all the images for a chapter

    Attributes:
        image_data (list[bytes]): The data of the images to merge
    """

    image_data: list[bytes]


@dataclass
class BenchmarkJob(Job):
    """
    A job for benchmarking the performance of a batch of jobs.

    Relays the start and end times of the jobs to the pipeline manager.
    """
