from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict

MAX_APP_PROPERTY_BYTES = 124


def _truncate_for_app_properties(key: str, value: str) -> str:
    """Truncate value to fit within Google Drive appProperties limit.

    Google Drive limits each property (key + value) to 124 bytes in UTF-8.
    This function ensures the value fits within that limit.
    """
    max_value_bytes = MAX_APP_PROPERTY_BYTES - len(key.encode("utf-8"))
    if max_value_bytes < 0:
        max_value_bytes = 0

    value_bytes = value.encode("utf-8")
    if len(value_bytes) <= max_value_bytes:
        return value

    return value_bytes[:max_value_bytes].decode("utf-8", errors="ignore")


class ClientNotInitializedError(Exception):
    """Raised when client methods are called before initialize()."""


class GoogleApiStoredToken(TypedDict):
    """Token data for google.oauth2.credentials.Credentials."""

    token_uri: str
    client_id: str
    client_secret: str
    refresh_token: str


class GoogleDriveDirectory(TypedDict):
    """Directory metadata from Google Drive API."""

    id: str
    name: str
    appProperties: dict[str, str] | None


class GoogleDriveFile(TypedDict):
    """File metadata from Google Drive API."""

    id: str
    name: str
    appProperties: dict[str, str] | None


@dataclass(frozen=True)
class InitResult:
    """Result from GoogleDriveClient.initialize()."""

    root_folder_id: str
    cached_folder_count: int
    was_created: bool


@dataclass(frozen=True)
class GoogleDriveFolderMetadata:
    """Immutable metadata for Google Drive folders."""

    source: str

    @classmethod
    def from_app_properties(cls, props: dict[str, str]) -> GoogleDriveFolderMetadata:
        if "source" not in props:
            raise ValueError("Missing source in appProperties")

        return cls(source=props["source"])

    def to_app_properties(self) -> dict[str, str]:
        return {"source": _truncate_for_app_properties("source", self.source)}


@dataclass(frozen=True)
class GoogleDriveFileMetadata:
    """Immutable metadata for Google Drive files."""

    source: str
    chapter_num: str
    chapter_title: str

    @classmethod
    def from_app_properties(cls, props: dict[str, str]) -> GoogleDriveFileMetadata:
        if "source" not in props:
            raise ValueError("Missing source in appProperties")

        if "chapter_num" not in props:
            raise ValueError("Missing chapter_num in appProperties")

        if "chapter_title" not in props:
            raise ValueError("Missing chapter_title in appProperties")

        return cls(
            source=props["source"],
            chapter_num=props["chapter_num"],
            chapter_title=props["chapter_title"],
        )

    def to_app_properties(self) -> dict[str, str]:
        return {
            "source": _truncate_for_app_properties("source", self.source),
            "chapter_num": self.chapter_num,
            "chapter_title": _truncate_for_app_properties("chapter_title", self.chapter_title),
        }
