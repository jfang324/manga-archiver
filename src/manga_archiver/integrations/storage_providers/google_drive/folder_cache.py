import asyncio
from dataclasses import dataclass


@dataclass(frozen=True)
class _MangaFolderKey:
    """Cache key for a manga folder."""

    source: str
    title: str


class GoogleDriveFolderCache:
    """Shared cache for Google Drive folder lookup state."""

    def __init__(self) -> None:
        self.root_folder_id: str | None = None
        self._folder_ids: dict[_MangaFolderKey, str] = {}
        self.lock = asyncio.Lock()

    def get_folder_id(self, source: str, title: str) -> str | None:
        """Return cached manga folder id, if present."""
        return self._folder_ids.get(_MangaFolderKey(source=source, title=title))

    def set_folder_id(self, source: str, title: str, folder_id: str) -> None:
        """Cache a manga folder id."""
        self._folder_ids[_MangaFolderKey(source=source, title=title)] = folder_id
