from dataclasses import dataclass

from .content_source import ContentSource


@dataclass(frozen=True)
class Manga:
    """Immutable data container representing a source-agnostic manga."""

    id: str
    title: str
    source: ContentSource
