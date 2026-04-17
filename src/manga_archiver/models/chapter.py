from dataclasses import dataclass

from .content_source import ContentSource


@dataclass(frozen=True)
class Chapter:
    """Immutable data container representing a source-agnostic chapter."""

    id: str
    title: str
    chapter_num: float
    source: ContentSource
