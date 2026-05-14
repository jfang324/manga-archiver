from unittest.mock import MagicMock, patch

import pytest
from googleapiclient.errors import HttpError

from src.manga_archiver.integrations.storage_providers.google_drive.constants import (
    DEFAULT_CHUNK_SIZE,
    MULTIPART_UPLOAD_THRESHOLD,
)
from src.manga_archiver.integrations.storage_providers.google_drive.sdk_client import (
    GoogleDriveSdkClient,
)
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleDriveFileMetadata,
)
from src.manga_archiver.persistence.google_drive_token_store import GoogleApiStoredToken


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
async def test_list_files_in_folder_returns_all_pages(_mock_build: MagicMock) -> None:
    sdk_client = _create_sdk_client()
    first_file = {"id": "file_1", "name": "Chapter 1", "appProperties": {}}
    second_file = {"id": "file_2", "name": "Chapter 2", "appProperties": {}}
    first_request = MagicMock()
    first_request.execute.return_value = {"files": [first_file], "nextPageToken": "next_page"}
    second_request = MagicMock()
    second_request.execute.return_value = {"files": [second_file]}
    files_resource = MagicMock()
    files_resource.list.side_effect = [first_request, second_request]
    sdk_client._service.files.return_value = files_resource

    files = await sdk_client.list_files_in_folder("folder_123", page_size=1)
    list_calls = files_resource.list.call_args_list

    assert files == [first_file, second_file]
    assert [call.kwargs["pageToken"] for call in list_calls] == [None, "next_page"]
    assert list_calls[0].kwargs["fields"] == "files(id, name, appProperties), nextPageToken"


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
async def test_upload_file_selects_upload_mode_by_file_size(
    _mock_build: MagicMock,
    file_size: int,
    chunk_size: int | None,
    expected_resumable: bool,
    expected_chunk_size: int | None,
) -> None:
    sdk_client = _create_sdk_client()
    files_resource = _set_upload_response(sdk_client, {"id": "file_123"})

    upload_kwargs: dict[str, int] = {}
    if chunk_size is not None:
        upload_kwargs["chunk_size"] = chunk_size

    file_id = await sdk_client.upload_file(
        file_data=b"x" * file_size,
        file_name="Test Manga [1].pdf",
        folder_id="folder_123",
        mimetype="application/pdf",
        app_properties=_file_metadata().to_app_properties(),
        **upload_kwargs,
    )

    create_kwargs = files_resource.create.call_args.kwargs
    media = create_kwargs["media_body"]
    assert file_id == "file_123"
    assert media.resumable() is expected_resumable
    if expected_chunk_size is not None:
        assert media.chunksize() == expected_chunk_size


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_upload_file_retries_conflict_with_same_upload_mode(
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

    file_id = await sdk_client.upload_file(
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
