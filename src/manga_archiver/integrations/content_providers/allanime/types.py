"""AllManga API response types."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class PictureUrl:
    """Mirrors pictureUrls[] items from chapter pages response."""

    url: str

    @classmethod
    def from_dict(cls, data: dict) -> PictureUrl:
        """Parse raw picture URL dict into typed object.

        Args:
            data: Raw picture URL dictionary from API response

        Returns:
            PictureUrl with parsed URL

        Raises:
            ValueError: If url is missing or empty
        """
        url = data.get("url")

        if not url:
            raise ValueError("Missing required field: url")

        return cls(url=url)


@dataclass
class ChapterPageEdge:
    """Mirrors chapterPages.edges[] items."""

    picture_urls: list[PictureUrl] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ChapterPageEdge:
        """Parse raw edge dict into typed object.

        Args:
            data: Raw edge dictionary from API response

        Returns:
            ChapterPageEdge with parsed picture URLs
        """
        picture_list = data.get("pictureUrls", [])
        picture_urls = [PictureUrl.from_dict(p) for p in picture_list]

        return cls(picture_urls=picture_urls)


@dataclass
class ChapterPagesData:
    """Mirrors decrypted chapterPages response."""

    edges: list[ChapterPageEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ChapterPagesData:
        """Parse raw chapterPages dict into typed object.

        Args:
            data: Raw chapterPages dictionary from decrypted API response

        Returns:
            ChapterPagesData with parsed edges
        """
        edges_list = data.get("edges", [])
        edges = [ChapterPageEdge.from_dict(e) for e in edges_list]

        return cls(edges=edges)


@dataclass
class SearchResult:
    """Mirrors data.mangas.edges[] items."""

    _id: str
    english_name: str | None
    name: str | None

    @classmethod
    def from_dict(cls, data: dict) -> SearchResult:
        """Parse raw edge dict into typed object.

        Args:
            data: Raw manga edge dictionary from search response

        Returns:
            SearchResult with id and name fields

        Raises:
            ValueError: If _id is missing or empty
        """
        manga_id = data.get("_id")
        if not manga_id:
            raise ValueError("Missing required field: _id")

        return cls(
            _id=manga_id,
            english_name=data.get("englishName"),
            name=data.get("name"),
        )

    @property
    def title(self) -> str:
        """Get display title, falling back to name if english_name is None."""
        return self.english_name or self.name or "unknown"


@dataclass
class MangaChaptersDetail:
    """Mirrors data.manga.availableChaptersDetail."""

    sub: list[str]

    @classmethod
    def from_dict(cls, data: dict) -> MangaChaptersDetail:
        """Parse raw availableChaptersDetail dict into typed object.

        Args:
            data: Raw availableChaptersDetail dictionary from manga response

        Returns:
            MangaChaptersDetail with parsed chapter strings

        Raises:
            ValueError: If sub is missing or empty
        """
        sub = data.get("sub")
        if not sub:
            raise ValueError("Missing required field: sub")

        return cls(sub=sub)
