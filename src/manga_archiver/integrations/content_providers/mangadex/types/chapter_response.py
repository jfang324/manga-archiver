from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ChapterResultAttributes:
    """Attributes from MangaDex chapter API."""

    chapter: float
    title: str

    @classmethod
    def from_dict(cls, attributes: dict) -> ChapterResultAttributes:
        """Create a ChapterResultAttributes from a dictionary."""
        if "chapter" not in attributes:
            raise ValueError("Invalid attributes: missing chapter")

        try:
            chapter = float(attributes["chapter"])
        except (ValueError, TypeError):
            raise ValueError("Invalid attributes: chapter failed to parse to float")

        return cls(
            chapter=chapter,
            title=attributes.get("title", "untitled"),
        )


@dataclass(frozen=True)
class ChapterResult:
    """Result from MangaDex chapter API."""

    id: str
    attributes: ChapterResultAttributes

    @classmethod
    def from_dict(cls, result: dict) -> ChapterResult:
        """Create a ChapterResult from a dictionary."""
        if "id" not in result:
            raise ValueError("Invalid result: missing id")

        if "attributes" not in result:
            raise ValueError("Invalid result: missing attributes")

        return cls(
            id=result["id"],
            attributes=ChapterResultAttributes.from_dict(result["attributes"]),
        )


@dataclass(frozen=True)
class MangaDexChapterResponse:
    """Response from MangaDex chapter API."""

    data: list[ChapterResult]

    @classmethod
    def from_dict(cls, response: dict) -> MangaDexChapterResponse:
        """Create a MangaDexChapterResponse from a dictionary."""
        if "data" not in response:
            raise ValueError("Invalid response: missing data")

        results: list[ChapterResult] = []

        for result in response["data"]:
            try:
                results.append(ChapterResult.from_dict(result))
            except ValueError:  # noqa: PERF203 - try catch is required to skip invalid results
                pass

        return cls(data=results)
