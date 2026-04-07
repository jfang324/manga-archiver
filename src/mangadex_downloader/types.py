from typing import TypedDict


class ProcessedManga(TypedDict):
    """Dictionary containing metadata for a manga."""

    id: str
    title: str


class ProcessedChapter(TypedDict):
    """Dictionary containing metadata for a chapter."""

    id: str
    title: str
    chapter: str


class ProcessedDownloadResource(TypedDict):
    """Dictionary containing metadata for a download resource."""

    hash: str
    urls: list[str]
