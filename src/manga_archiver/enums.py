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
