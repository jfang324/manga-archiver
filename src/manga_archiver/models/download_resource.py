from dataclasses import dataclass

from .content_source import ContentSource


@dataclass(frozen=True)
class DownloadResource:
    """Immutable data container representing a source-agnostic download resource."""

    urls: list[str]
    source: ContentSource
