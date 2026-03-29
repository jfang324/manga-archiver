"""Type definitions for processed data from MangaDex API."""

from typing import Optional, TypedDict


class ProcessedManga(TypedDict):
    """Processed manga data from search results."""

    title: str
    id: str


class ProcessedChapter(TypedDict):
    """Processed chapter data from feed."""

    title: Optional[str]
    id: str
    chapter: str


class ProcessedDownloadResource(TypedDict):
    """Processed download resource containing image URLs."""

    urls: list[str]
    hash: str
