from enum import Enum


class ContentSource(Enum):
    """Provider source identifier for all content."""

    MANGADEX = "mangadex"
    ALLMANGA = "allmanga"

    def __str__(self) -> str:
        return self.value
