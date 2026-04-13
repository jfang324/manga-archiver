from dataclasses import dataclass
from enum import Enum
from typing import TypedDict


class ContentSource(Enum):
    """Provider source identifier for all content."""

    MANGADEX = "mangadex"


# Old types (for backwards compatibility)
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


# New types
@dataclass
class Manga:
    """Data container representing a source-agnostic manga."""

    id: str
    title: str
    source: ContentSource


@dataclass
class Chapter:
    """Data container representing a source-agnostic chapter."""

    id: str
    title: str
    chapter_num: float
    source: ContentSource


@dataclass
class DownloadResource:
    """Data container representing a source-agnostic download resource."""

    urls: list[str]
    source: ContentSource
