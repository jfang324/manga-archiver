from dataclasses import dataclass

from ..models import ContentSource


@dataclass(frozen=True)
class FavoriteManga:
    """Immutable dataclass containing metadata for a favorite manga.

    Note: Matches the Manga(models/manga.py) type for now but represents
    database records which may be expanded in the future.
    """

    id: str
    title: str
    source: ContentSource
