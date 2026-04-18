from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResourceBundle:
    """Resource bundle from MangaDex download resource API."""

    hash: str
    data: list[str]
    data_saver: list[str] | None

    @classmethod
    def from_dict(cls, bundle: dict) -> ResourceBundle:
        """Create a ResourceBundle from a dictionary."""
        if "hash" not in bundle:
            raise ValueError("Invalid bundle: missing hash")

        if "data" not in bundle:
            raise ValueError("Invalid bundle: missing data")

        return cls(
            hash=bundle["hash"],
            data=bundle["data"],
            data_saver=bundle.get("dataSaver"),
        )


@dataclass(frozen=True)
class MangaDexDownloadResourceResponse:
    """Response from MangaDex download resource API."""

    base_url: str
    chapter: ResourceBundle

    @classmethod
    def from_dict(cls, response: dict) -> MangaDexDownloadResourceResponse:
        """Create a MangaDexDownloadResourceResponse from a dictionary."""
        if "baseUrl" not in response:
            raise ValueError("Invalid response: missing baseUrl")

        if "chapter" not in response:
            raise ValueError("Invalid response: missing chapter")

        return cls(
            base_url=response["baseUrl"],
            chapter=ResourceBundle.from_dict(response["chapter"]),
        )
