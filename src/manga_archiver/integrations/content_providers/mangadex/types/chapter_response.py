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

        title = "untitled"

        if (
            "title" in attributes
            and isinstance(attributes["title"], str)
            and attributes["title"].strip()
        ):
            title = attributes["title"]

        return cls(
            chapter=chapter,
            title=title,
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

        if not isinstance(response["data"], list):
            raise ValueError("Invalid response: data must be a list")

        results: list[ChapterResult] = []

        for result in response["data"]:
            if not isinstance(result, dict):
                continue

            try:
                results.append(ChapterResult.from_dict(result))
            except ValueError:
                pass

        return cls(data=results)
