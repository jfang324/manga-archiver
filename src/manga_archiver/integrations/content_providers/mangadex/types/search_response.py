from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResultAttributes:
    """Attributes from MangaDex search API."""

    title: str

    @classmethod
    def from_dict(cls, attributes: dict) -> SearchResultAttributes:
        """Create a SearchResultAttributes from a dictionary."""
        if "title" not in attributes or not attributes["title"]:
            return cls(title="unknown")

        title: str = "unknown"

        # English title is not always present
        if "en" in attributes["title"]:
            title = attributes["title"]["en"]
        else:
            first_key = next(iter(attributes["title"]))
            title = attributes["title"][first_key]

        return cls(title=title)


@dataclass(frozen=True)
class SearchResult:
    """Result from MangaDex search API."""

    id: str
    attributes: SearchResultAttributes

    @classmethod
    def from_dict(cls, result: dict) -> SearchResult:
        """Create a SearchResult from a dictionary."""
        if "id" not in result:
            raise ValueError("Invalid result: missing id")

        if "attributes" not in result:
            raise ValueError("Invalid result: missing attributes")

        return cls(
            id=result["id"], attributes=SearchResultAttributes.from_dict(result["attributes"])
        )


@dataclass(frozen=True)
class MangaDexSearchResponse:
    """Response from MangaDex search API."""

    data: list[SearchResult]

    @classmethod
    def from_dict(cls, response: dict) -> MangaDexSearchResponse:
        """Create a MangaDexSearchResponse from a dictionary."""
        if "data" not in response:
            raise ValueError("Invalid response: missing data")

        if not isinstance(response["data"], list):
            raise ValueError("Invalid response: data must be a list")

        results: list[SearchResult] = []

        for result in response["data"]:
            if not isinstance(result, dict):
                continue

            try:
                results.append(SearchResult.from_dict(result))
            except ValueError:
                pass

        return cls(data=results)
