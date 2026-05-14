from __future__ import annotations

from typing import TYPE_CHECKING

from .constants import DEFAULT_MAX_RETRIES, DEFAULT_ROOT_PAGE_SIZE, ROOT_FOLDER_NAME, SYSTEM_SOURCE
from .sdk_client import GoogleDriveSdkClient
from .types import (
    GoogleDriveDirectory,
    GoogleDriveFile,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
    InitResult,
)

if TYPE_CHECKING:
    from ....persistence.google_drive_token_store import GoogleApiStoredToken


class GoogleDriveMigrationClient:
    """Google Drive operations needed by database migrations."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._sdk_client = GoogleDriveSdkClient(stored_token, max_retries)

    async def initialize(self) -> InitResult:
        """Initialize root folder context for migration operations."""
        root_folders = await self._sdk_client.list_root_folders(
            ROOT_FOLDER_NAME, page_size=DEFAULT_ROOT_PAGE_SIZE
        )

        root_folder_id = None
        was_created = False
        for folder in root_folders:
            if folder["name"] == ROOT_FOLDER_NAME:
                root_folder_id = folder["id"]
                break

        if root_folder_id is None:
            root_metadata = GoogleDriveFolderMetadata(source=SYSTEM_SOURCE)
            root_folder_id = await self._sdk_client.create_folder(
                ROOT_FOLDER_NAME, folder_metadata=root_metadata
            )
            was_created = True

        return InitResult(
            root_folder_id=root_folder_id,
            cached_folder_count=0,
            was_created=was_created,
        )

    async def list_child_folders(self, parent_id: str) -> list[GoogleDriveDirectory]:
        """List child folders under a parent folder."""
        return await self._sdk_client.list_sub_folders(parent_id)

    async def list_files(self, folder_id: str) -> list[GoogleDriveFile]:
        """List files under a manga folder."""
        return await self._sdk_client.list_files_in_folder(folder_id)

    async def update_folder_metadata(
        self, folder_id: str, metadata: GoogleDriveFolderMetadata
    ) -> None:
        """Update migration metadata on a folder."""
        await self._sdk_client.update_metadata(folder_id, metadata.to_app_properties())

    async def update_file_metadata(self, file_id: str, metadata: GoogleDriveFileMetadata) -> None:
        """Update migration metadata on a file."""
        await self._sdk_client.update_metadata(file_id, metadata.to_app_properties())
