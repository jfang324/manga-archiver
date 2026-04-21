from __future__ import annotations

from dataclasses import dataclass
from typing import TypedDict


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
        return {"source": self.source}


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
            "source": self.source,
            "chapter_num": self.chapter_num,
            "chapter_title": self.chapter_title,
        }
