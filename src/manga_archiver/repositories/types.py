from typing import TypedDict

from ..types import ContentSource


class FavoriteManga(TypedDict):
    """Dictionary containing metadata for a favorite manga."""

    id: str
    title: str
    source: ContentSource
