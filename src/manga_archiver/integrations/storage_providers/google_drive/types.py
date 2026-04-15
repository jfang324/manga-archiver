from dataclasses import dataclass
from typing import TypedDict


class GoogleApiStoredToken(TypedDict):
    """Dictionary containing metadata for google.oauth2.credentials.Credentials."""

    token_uri: str
    client_id: str
    client_secret: str
    refresh_token: str


class GoogleDriveDirectory(TypedDict):
    """Dictionary containing metadata for a Google Drive directory."""

    id: str
    name: str
    appProperties: dict[str, str] | None


@dataclass(frozen=True)
class GoogleDriveFolderMetadata:
    """Immutable metadata for Google Drive folders."""

    source: str

    def to_app_properties(self) -> dict[str, str]:
        return {"source": self.source}


@dataclass(frozen=True)
class GoogleDriveFileMetadata:
    """Immutable metadata for Google Drive files."""

    source: str
    chapter_num: str
    chapter_title: str

    def to_app_properties(self) -> dict[str, str]:
        return {
            "source": self.source,
            "chapter_num": self.chapter_num,
            "chapter_title": self.chapter_title,
        }
