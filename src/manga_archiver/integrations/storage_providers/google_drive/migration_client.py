from .constants import DEFAULT_MAX_RETRIES, DEFAULT_ROOT_PAGE_SIZE, ROOT_FOLDER_NAME, SYSTEM_SOURCE
from .sdk_client import GoogleDriveSdkClient
from .types import (
    GoogleApiStoredToken,
    GoogleDriveDirectory,
    GoogleDriveFile,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
    InitResult,
)


class GoogleDriveMigrationClient:
    """Google Drive operations needed by database migrations."""

    def __init__(
        self,
        stored_token: GoogleApiStoredToken,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ) -> None:
        self._sdk_client = GoogleDriveSdkClient(stored_token, max_retries)

    def initialize(self) -> InitResult:
        """Initialize root folder context for migration operations."""
        root_folders = self._sdk_client.list_root_folders(
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
            # TODO: Use async SDK folder creation after migrations can become async.  # noqa: FIX002
            root_folder_id = self._sdk_client._create_folder_sync(
                ROOT_FOLDER_NAME, folder_metadata=root_metadata
            )
            was_created = True

        return InitResult(
            root_folder_id=root_folder_id,
            cached_folder_count=0,
            was_created=was_created,
        )

    def list_child_folders(self, parent_id: str) -> list[GoogleDriveDirectory]:
        """List child folders under a parent folder."""
        return self._sdk_client.list_sub_folders(parent_id)

    def list_files(self, folder_id: str) -> list[GoogleDriveFile]:
        """List files under a manga folder."""
        return self._sdk_client.list_files_in_folder(folder_id)

    def update_folder_metadata(self, folder_id: str, metadata: GoogleDriveFolderMetadata) -> None:
        """Update migration metadata on a folder."""
        self._sdk_client.update_metadata(folder_id, metadata.to_app_properties())

    def update_file_metadata(self, file_id: str, metadata: GoogleDriveFileMetadata) -> None:
        """Update migration metadata on a file."""
        self._sdk_client.update_metadata(file_id, metadata.to_app_properties())
