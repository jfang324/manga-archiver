from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.integrations.storage_providers.google_drive.migration_client import (
    GoogleDriveMigrationClient,
)
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleApiStoredToken,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
)


def _token() -> GoogleApiStoredToken:
    return {
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


def _file_metadata() -> GoogleDriveFileMetadata:
    return GoogleDriveFileMetadata(
        source="mangadex",
        chapter_num="1",
        chapter_title="Chapter 1",
    )


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
@pytest.mark.parametrize(
    ("client_method", "sdk_method", "item_id"),
    [
        ("list_child_folders", "list_sub_folders", "root_123"),
        ("list_files", "list_files_in_folder", "folder_123"),
    ],
    ids=["child-folders", "files"],
)
async def test_migration_client_delegates_listing(
    _mock_build: MagicMock,
    client_method: str,
    sdk_method: str,
    item_id: str,
) -> None:
    client = GoogleDriveMigrationClient(_token())
    client._sdk_client.list_sub_folders = AsyncMock(return_value=[])
    client._sdk_client.list_files_in_folder = AsyncMock(return_value=[])

    result = await getattr(client, client_method)(item_id)

    assert result == []
    getattr(client._sdk_client, sdk_method).assert_awaited_once_with(item_id)


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
@pytest.mark.parametrize(
    ("client_method", "item_id", "metadata"),
    [
        ("update_folder_metadata", "folder_123", GoogleDriveFolderMetadata(source="mangadex")),
        ("update_file_metadata", "file_123", _file_metadata()),
    ],
    ids=["folder", "file"],
)
async def test_migration_client_delegates_metadata_updates(
    _mock_build: MagicMock,
    client_method: str,
    item_id: str,
    metadata: GoogleDriveFolderMetadata | GoogleDriveFileMetadata,
) -> None:
    client = GoogleDriveMigrationClient(_token())
    client._sdk_client.update_metadata = AsyncMock()

    await getattr(client, client_method)(item_id, metadata)

    client._sdk_client.update_metadata.assert_awaited_once_with(
        item_id,
        metadata.to_app_properties(),
    )
