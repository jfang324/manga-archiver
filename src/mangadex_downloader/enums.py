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


class OutputFormat(Enum):
    """An enum class for the supported output formats."""

    PDF = "pdf"
    CBZ = "cbz"
    EPUB = "epub"

    def __str__(self) -> str:
        return self.value

    @classmethod
    def list_formats(cls) -> list[str]:
        return [format.value for format in cls]
