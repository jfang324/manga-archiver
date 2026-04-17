from dataclasses import dataclass

from ..models import ContentSource


@dataclass(frozen=True)
class FavoriteManga:
    """Immutable dataclass containing metadata for a favorite manga."""

    id: str
    title: str
    source: ContentSource
