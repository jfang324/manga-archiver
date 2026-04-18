from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class PictureUrl:
    """Mirrors pictureUrls[] items from chapter pages response."""

    url: str

    @classmethod
    def from_dict(cls, data: dict) -> PictureUrl:
        """Create a PictureUrl from a dictionary."""
        if "url" not in data:
            raise ValueError("Invalid picture URL: missing url")

        url = data["url"]
        if not url:
            raise ValueError("Invalid picture URL: empty url")

        return cls(url=url)


@dataclass(frozen=True)
class ChapterPageEdge:
    """Mirrors chapterPages.edges[] items."""

    picture_urls: list[PictureUrl] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ChapterPageEdge:
        """Create a ChapterPageEdge from a dictionary."""
        if "pictureUrls" not in data:
            raise ValueError("Invalid chapter edge: missing pictureUrls")

        picture_list = data["pictureUrls"]
        if not isinstance(picture_list, list):
            raise ValueError("Invalid chapter edge: pictureUrls must be a list")

        picture_urls: list[PictureUrl] = []
        for p in picture_list:
            if not isinstance(p, dict):
                continue
            try:
                picture_urls.append(PictureUrl.from_dict(p))
            except ValueError:  # noqa: PERF203 - skip invalid picture URLs
                pass

        return cls(picture_urls=picture_urls)


@dataclass(frozen=True)
class ChapterPagesData:
    """Mirrors decrypted chapterPages response."""

    edges: list[ChapterPageEdge] = field(default_factory=list)

    @classmethod
    def from_dict(cls, data: dict) -> ChapterPagesData:
        """Create a ChapterPagesData from a dictionary."""
        if "edges" not in data:
            raise ValueError("Invalid chapter pages: missing edges")

        edges_list = data["edges"]
        if not isinstance(edges_list, list):
            raise ValueError("Invalid chapter pages: edges must be a list")

        edges: list[ChapterPageEdge] = []
        for e in edges_list:
            if not isinstance(e, dict):
                continue
            try:
                edges.append(ChapterPageEdge.from_dict(e))
            except ValueError:  # noqa: PERF203 - skip invalid chapter edges
                pass

        return cls(edges=edges)


@dataclass(frozen=True)
class DownloadResourceResponse:
    """Mirrors data.chapterPages container."""

    pages: ChapterPagesData

    @classmethod
    def from_dict(cls, response: dict) -> DownloadResourceResponse:
        """Create a DownloadResourceResponse from a dictionary."""
        if "chapterPages" not in response:
            raise ValueError("Invalid response: missing chapterPages")

        chapter_pages = response["chapterPages"]
        if not isinstance(chapter_pages, dict):
            raise ValueError("Invalid response: chapterPages is not a dict")

        pages = ChapterPagesData.from_dict(chapter_pages)

        return cls(pages=pages)
