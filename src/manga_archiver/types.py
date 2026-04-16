from dataclasses import dataclass
from enum import Enum


class ContentSource(Enum):
    """Provider source identifier for all content."""

    MANGADEX = "mangadex"
    ALLMANGA = "allmanga"

    def __str__(self) -> str:
        return self.value


@dataclass(frozen=True)
class Manga:
    """Immutable data container representing a source-agnostic manga."""

    id: str
    title: str
    source: ContentSource


@dataclass(frozen=True)
class Chapter:
    """Immutable data container representing a source-agnostic chapter."""

    id: str
    title: str
    chapter_num: float
    source: ContentSource


@dataclass(frozen=True)
class DownloadResource:
    """Immutable data container representing a source-agnostic download resource."""

    urls: list[str]
    source: ContentSource
