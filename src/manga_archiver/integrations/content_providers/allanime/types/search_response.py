from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SearchResult:
    """Mirrors data.mangas.edges[] items."""

    _id: str
    english_name: str | None
    name: str | None

    @classmethod
    def from_dict(cls, data: dict) -> SearchResult:
        """Create a SearchResult from a dictionary."""
        if "_id" not in data:
            raise ValueError("Invalid search result: missing _id")

        _id = data["_id"]
        if not isinstance(_id, str):
            raise ValueError("Invalid search result: _id must be a string")

        return cls(
            _id=_id,
            english_name=data.get("englishName"),
            name=data.get("name"),
        )

    @property
    def title(self) -> str:
        """Get display title, falling back to name if english_name is None."""
        return self.english_name or self.name or "unknown"


@dataclass(frozen=True)
class SearchEdges:
    """Mirrors data.mangas container."""

    edges: list[SearchResult]

    @classmethod
    def from_dict(cls, data: dict) -> SearchEdges:
        """Create a SearchEdges from a dictionary."""
        if "mangas" not in data:
            raise ValueError("Invalid response: missing mangas")

        manga_data = data["mangas"]
        if not isinstance(manga_data, dict):
            raise ValueError("Invalid response: mangas is not a dict")

        if "edges" not in manga_data:
            raise ValueError("Invalid response: missing edges")

        edges_data = manga_data["edges"]
        if not isinstance(edges_data, list):
            raise ValueError("Invalid response: edges must be a list")

        results: list[SearchResult] = []
        for edge in edges_data:
            if not isinstance(edge, dict):
                continue
            try:
                results.append(SearchResult.from_dict(edge))
            except ValueError:  # noqa: PERF203 - skip invalid entries
                pass

        return cls(edges=results)


@dataclass(frozen=True)
class AllMangaSearchResponse:
    """Response from AllManga search API."""

    data: SearchEdges

    @classmethod
    def from_dict(cls, response: dict) -> AllMangaSearchResponse:
        """Create an AllMangaSearchResponse from a dictionary."""
        if "data" not in response:
            raise ValueError("Invalid response: missing data")

        root = response["data"]

        if not isinstance(root, dict):
            raise ValueError("Invalid response: data is not a dict")

        return cls(data=SearchEdges.from_dict(root))
