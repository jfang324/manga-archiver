from dataclasses import dataclass
from enum import Enum


class ContentSource(Enum):
    """Provider source identifier for all content."""

    MANGADEX = "mangadex"

    def __str__(self) -> str:
        return self.value


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
