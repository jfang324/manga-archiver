import asyncio
from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.manga_archiver.integrations.storage_providers.google_drive.client import GoogleDriveClient
from src.manga_archiver.integrations.storage_providers.google_drive.constants import (
    DEFAULT_CHUNK_SIZE,
    MULTIPART_UPLOAD_THRESHOLD,
    ROOT_FOLDER_NAME,
)
from src.manga_archiver.integrations.storage_providers.google_drive.sdk_client import (
    GoogleDriveSdkClient,
)
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleApiStoredToken,
    GoogleDriveFileMetadata,
)


def _reset_google_drive_client_cache() -> None:
    GoogleDriveClient._root_folder_id = None
    GoogleDriveClient._folder_cache = {}
    GoogleDriveClient._folder_cache_lock = asyncio.Lock()


@pytest.fixture(autouse=True)
def reset_google_drive_client_cache() -> Generator[None, None, None]:
    _reset_google_drive_client_cache()
    yield
    _reset_google_drive_client_cache()


def _token() -> GoogleApiStoredToken:
    return {
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


def _create_client() -> GoogleDriveClient:
    return GoogleDriveClient(_token())


def _file_metadata() -> GoogleDriveFileMetadata:
    return GoogleDriveFileMetadata(
        source="mangadex",
        chapter_num="1",
        chapter_title="Chapter 1",
    )


def _create_sdk_client() -> GoogleDriveSdkClient:
    return GoogleDriveSdkClient(_token())


def _set_upload_response(sdk_client: GoogleDriveSdkClient, response: dict[str, str]) -> MagicMock:
    create_request = MagicMock()
    create_request.execute.return_value = response
    files_resource = MagicMock()
    files_resource.create.return_value = create_request
    sdk_client._service.files.return_value = files_resource

    return files_resource


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
def test_initialize_cache_is_visible_to_other_client_instance(
    _mock_build: MagicMock,
) -> None:
    first_client = _create_client()
    first_client._get_root_folders = MagicMock(
        return_value=[{"id": "root_123", "name": ROOT_FOLDER_NAME, "appProperties": {}}]
    )
    first_client._get_sub_folders = MagicMock(
        return_value=[
            {
                "id": "folder_123",
                "name": "Test Manga",
                "appProperties": {"source": "mangadex"},
            }
        ]
    )

    init_result = first_client.initialize()
    second_client = _create_client()

    assert init_result.root_folder_id == "root_123"
    assert init_result.cached_folder_count == 1
    assert second_client.get_manga_folder_id("Test Manga", "mangadex") == "folder_123"


@pytest.mark.asyncio
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_get_or_create_manga_folder_caches_search_result(
    _mock_build: MagicMock,
) -> None:
    GoogleDriveClient._root_folder_id = "root_123"
    client = _create_client()
    client._sdk_client.search_folder_by_name = AsyncMock(return_value="folder_123")
    client._sdk_client.create_folder = AsyncMock()

    first_folder_id = await client.get_or_create_manga_folder("Test Manga", "mangadex")
    second_folder_id = await client.get_or_create_manga_folder("Test Manga", "mangadex")

    assert first_folder_id == "folder_123"
    assert second_folder_id == "folder_123"
    client._sdk_client.search_folder_by_name.assert_awaited_once_with(
        "Test Manga", "root_123", "mangadex"
    )
    client._sdk_client.create_folder.assert_not_awaited()


@pytest.mark.asyncio
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_concurrent_get_or_create_manga_folder_creates_one_folder(
    _mock_build: MagicMock,
) -> None:
    GoogleDriveClient._root_folder_id = "root_123"
    client = _create_client()
    client._sdk_client.search_folder_by_name = AsyncMock(return_value=None)
    client._sdk_client.create_folder = AsyncMock(return_value="folder_123")

    results = await asyncio.gather(
        client.get_or_create_manga_folder("Test Manga", "mangadex"),
        client.get_or_create_manga_folder("Test Manga", "mangadex"),
    )

    assert results == ["folder_123", "folder_123"]
    client._sdk_client.search_folder_by_name.assert_awaited_once_with(
        "Test Manga", "root_123", "mangadex"
    )
    client._sdk_client.create_folder.assert_awaited_once()


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
@pytest.mark.parametrize(
    (
        "file_size",
        "chunk_size",
        "expected_resumable",
        "expected_chunk_size",
    ),
    [
        (
            MULTIPART_UPLOAD_THRESHOLD,
            None,
            False,
            None,
        ),
        (
            MULTIPART_UPLOAD_THRESHOLD + 1,
            None,
            True,
            DEFAULT_CHUNK_SIZE,
        ),
        (
            MULTIPART_UPLOAD_THRESHOLD + 1,
            DEFAULT_CHUNK_SIZE * 2,
            True,
            DEFAULT_CHUNK_SIZE * 2,
        ),
    ],
    ids=[
        "small_uses_multipart",
        "large_uses_default_resumable_chunk_size",
        "large_allows_custom_resumable_chunk_size",
    ],
)
def test_upload_file_sync_selects_upload_mode_by_file_size(
    _mock_build: MagicMock,
    file_size: int,
    chunk_size: int | None,
    expected_resumable: bool,
    expected_chunk_size: int | None,
) -> None:
    sdk_client = _create_sdk_client()
    files_resource = _set_upload_response(sdk_client, {"id": "file_123"})

    kwargs = {}
    if chunk_size is not None:
        kwargs["chunk_size"] = chunk_size

    file_id = sdk_client._upload_file_sync(
        file_data=b"x" * file_size,
        file_name="Test Manga [1].pdf",
        folder_id="folder_123",
        mimetype="application/pdf",
        app_properties=_file_metadata().to_app_properties(),
        **kwargs,
    )

    create_kwargs = files_resource.create.call_args.kwargs
    media = create_kwargs["media_body"]
    assert file_id == "file_123"
    assert media.resumable() is expected_resumable
    if expected_chunk_size is not None:
        assert media.chunksize() == expected_chunk_size


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
def test_upload_file_sync_retries_conflict_with_same_upload_mode(
    _mock_build: MagicMock,
) -> None:
    sdk_client = _create_sdk_client()
    conflict = HttpError(MagicMock(status=409), b"conflict")
    first_request = MagicMock()
    first_request.execute.side_effect = conflict
    second_request = MagicMock()
    second_request.execute.return_value = {"id": "file_456"}
    files_resource = MagicMock()
    files_resource.create.side_effect = [first_request, second_request]
    sdk_client._service.files.return_value = files_resource

    file_id = sdk_client._upload_file_sync(
        file_data=b"x" * MULTIPART_UPLOAD_THRESHOLD,
        file_name="Test Manga [1].pdf",
        folder_id="folder_123",
        mimetype="application/pdf",
        app_properties=_file_metadata().to_app_properties(),
    )

    first_media = files_resource.create.call_args_list[0].kwargs["media_body"]
    second_call_kwargs = files_resource.create.call_args_list[1].kwargs
    second_media = second_call_kwargs["media_body"]
    assert file_id == "file_456"
    assert first_media.resumable() is False
    assert second_media.resumable() is False
    assert second_call_kwargs["body"]["name"] == "Test Manga [1] (1).pdf"
    assert second_call_kwargs["fields"] == "id"
