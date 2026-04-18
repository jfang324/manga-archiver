from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MangaChaptersDetail:
    """Mirrors data.manga.availableChaptersDetail."""

    sub: list[float]

    @classmethod
    def from_dict(cls, data: dict) -> MangaChaptersDetail:
        """Create a MangaChaptersDetail from a dictionary."""
        if "sub" not in data:
            raise ValueError("Invalid chapters detail: missing sub")

        raw_sub = data["sub"]
        if not isinstance(raw_sub, list):
            raise ValueError("Invalid chapters detail: sub must be a list")

        valid_sub: list[float] = []
        for chapter_str in raw_sub:
            if not isinstance(chapter_str, str):
                continue
            try:
                valid_sub.append(float(chapter_str))
            except ValueError:  # noqa: PERF203 - skip invalid chapter strings
                pass

        return cls(sub=valid_sub)


@dataclass(frozen=True)
class ChapterResponse:
    """Mirrors data.manga container."""

    detail: MangaChaptersDetail

    @classmethod
    def from_dict(cls, response: dict) -> ChapterResponse:
        """Create a ChapterResponse from a dictionary."""
        if "manga" not in response:
            raise ValueError("Invalid response: missing manga")

        manga_data = response["manga"]
        if not isinstance(manga_data, dict):
            raise ValueError("Invalid response: manga is not a dict")

        if "availableChaptersDetail" not in manga_data:
            raise ValueError("Invalid response: missing availableChaptersDetail")

        chapters_detail = manga_data["availableChaptersDetail"]

        if not isinstance(chapters_detail, dict):
            raise ValueError("Invalid response: availableChaptersDetail is not a dict")

        detail = MangaChaptersDetail.from_dict(chapters_detail)

        return cls(detail=detail)


@dataclass(frozen=True)
class AllMangaChapterResponse:
    """Response from AllManga chapter API."""

    data: ChapterResponse

    @classmethod
    def from_dict(cls, response: dict) -> AllMangaChapterResponse:
        """Create an AllMangaChapterResponse from a dictionary."""
        if "data" not in response:
            raise ValueError("Invalid response: missing data")

        root = response["data"]
        return cls(data=ChapterResponse.from_dict(root))
