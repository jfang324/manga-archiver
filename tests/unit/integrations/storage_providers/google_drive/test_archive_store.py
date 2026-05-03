import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.integrations.storage_providers.google_drive.archive_store import (
    GoogleDriveArchiveStore,
)
from src.manga_archiver.integrations.storage_providers.google_drive.constants import (
    DEFAULT_CHUNK_SIZE,
    ROOT_FOLDER_NAME,
)
from src.manga_archiver.integrations.storage_providers.google_drive.folder_cache import (
    GoogleDriveFolderCache,
)
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    ClientNotInitializedError,
    GoogleApiStoredToken,
    GoogleDriveFile,
)


def _token() -> GoogleApiStoredToken:
    return {
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


def _create_archive_store(folder_cache: GoogleDriveFolderCache) -> GoogleDriveArchiveStore:
    return GoogleDriveArchiveStore(_token(), folder_cache=folder_cache)


async def _upload_chapter(
    store: GoogleDriveArchiveStore,
    chapter_num: str = "1",
    file_name: str | None = None,
) -> str | None:
    return await store.upload_chapter(
        file_data=b"pdf",
        file_name=file_name or f"Test Manga [{chapter_num}].pdf",
        manga_title="Test Manga",
        source="mangadex",
        chapter_num=chapter_num,
        chapter_title=f"Chapter {chapter_num}",
        mimetype="application/pdf",
    )


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_initialize_cache_is_visible_to_other_archive_store_instance(
    _mock_build: MagicMock,
) -> None:
    folder_cache = GoogleDriveFolderCache()
    first_store = _create_archive_store(folder_cache)
    first_store._sdk_client.list_root_folders = AsyncMock(
        return_value=[{"id": "root_123", "name": ROOT_FOLDER_NAME, "appProperties": {}}]
    )
    first_store._sdk_client.list_sub_folders = AsyncMock(
        return_value=[
            {
                "id": "folder_123",
                "name": "Test Manga",
                "appProperties": {"source": "mangadex"},
            }
        ]
    )

    init_result = await first_store.initialize()
    second_store = _create_archive_store(folder_cache)

    assert init_result.root_folder_id == "root_123"
    assert init_result.cached_folder_count == 1
    assert await second_store.get_archived_chapter_numbers("Missing Manga", "mangadex") == []
    assert folder_cache.get_folder_id("mangadex", "Test Manga") == "folder_123"


@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_get_archived_chapter_numbers_returns_empty_without_cached_folder(
    _mock_build: MagicMock,
) -> None:
    folder_cache = GoogleDriveFolderCache()
    store = _create_archive_store(folder_cache)
    store._sdk_client.list_files_in_folder = AsyncMock()

    chapter_numbers = await store.get_archived_chapter_numbers("Missing Manga", "mangadex")

    assert chapter_numbers == []
    store._sdk_client.list_files_in_folder.assert_not_awaited()


@pytest.mark.parametrize(
    ("file", "expected_chapter_numbers"),
    [
        (
            {"id": "file_1", "name": "Chapter 1", "appProperties": {"chapter_num": "1"}},
            [1.0],
        ),
        ({"id": "file_2", "name": "No Properties", "appProperties": None}, []),
        ({"id": "file_3", "name": "Empty Properties", "appProperties": {}}, []),
        ({"id": "file_4", "name": "Missing Number", "appProperties": {"source": "mangadex"}}, []),
        (
            {
                "id": "file_5",
                "name": "Invalid Number",
                "appProperties": {"chapter_num": "not-a-number"},
            },
            [],
        ),
    ],
    ids=[
        "valid",
        "missing-properties",
        "empty-properties",
        "missing-chapter-num",
        "invalid-chapter-num",
    ],
)
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_get_archived_chapter_numbers_parses_valid_files_and_skips_invalid_files(
    _mock_build: MagicMock,
    file: GoogleDriveFile,
    expected_chapter_numbers: list[float],
) -> None:
    folder_cache = GoogleDriveFolderCache()
    folder_cache.set_folder_id("mangadex", "Test Manga", "folder_123")
    store = _create_archive_store(folder_cache)
    store._sdk_client.list_files_in_folder = AsyncMock(return_value=[file])

    chapter_numbers = await store.get_archived_chapter_numbers("Test Manga", "mangadex")

    assert chapter_numbers == expected_chapter_numbers
    store._sdk_client.list_files_in_folder.assert_awaited_once_with("folder_123", 1000)


@pytest.mark.asyncio
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_upload_chapter_caches_search_result(
    _mock_build: MagicMock,
) -> None:
    folder_cache = GoogleDriveFolderCache()
    folder_cache.root_folder_id = "root_123"
    store = _create_archive_store(folder_cache)
    store._sdk_client.search_folder_by_name = AsyncMock(return_value="folder_123")
    store._sdk_client.create_folder = AsyncMock()
    store._sdk_client.upload_file = AsyncMock(return_value="file_123")

    first_file_id = await _upload_chapter(store, chapter_num="1")
    second_file_id = await _upload_chapter(store, chapter_num="2")

    assert first_file_id == "file_123"
    assert second_file_id == "file_123"
    store._sdk_client.search_folder_by_name.assert_awaited_once_with(
        "Test Manga", "root_123", "mangadex"
    )
    store._sdk_client.create_folder.assert_not_awaited()
    assert store._sdk_client.upload_file.await_count == 2
    first_upload_args = store._sdk_client.upload_file.await_args_list[0].args
    assert first_upload_args == (
        b"pdf",
        "Test Manga [1].pdf",
        "folder_123",
        "application/pdf",
        {
            "source": "mangadex",
            "chapter_num": "1",
            "chapter_title": "Chapter 1",
        },
        DEFAULT_CHUNK_SIZE,
    )


@pytest.mark.asyncio
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_concurrent_upload_chapter_creates_one_folder(
    _mock_build: MagicMock,
) -> None:
    folder_cache = GoogleDriveFolderCache()
    folder_cache.root_folder_id = "root_123"
    store = _create_archive_store(folder_cache)
    store._sdk_client.search_folder_by_name = AsyncMock(return_value=None)
    store._sdk_client.create_folder = AsyncMock(return_value="folder_123")
    store._sdk_client.upload_file = AsyncMock(return_value="file_123")

    results = await asyncio.gather(
        _upload_chapter(store, chapter_num="1"),
        _upload_chapter(store, chapter_num="2"),
    )

    assert results == ["file_123", "file_123"]
    store._sdk_client.search_folder_by_name.assert_awaited_once_with(
        "Test Manga", "root_123", "mangadex"
    )
    store._sdk_client.create_folder.assert_awaited_once()
    create_folder_call = store._sdk_client.create_folder.await_args
    assert create_folder_call is not None
    create_folder_args = create_folder_call.args
    assert create_folder_args[0] == "Test Manga"
    assert create_folder_args[1].to_app_properties() == {"source": "mangadex"}
    assert create_folder_args[2] == "root_123"
    assert store._sdk_client.upload_file.await_count == 2
    upload_calls = store._sdk_client.upload_file.await_args_list
    assert [call.args[2] for call in upload_calls] == ["folder_123", "folder_123"]
    assert [call.args[4]["chapter_num"] for call in upload_calls] == ["1", "2"]


@pytest.mark.asyncio
@patch("src.manga_archiver.integrations.storage_providers.google_drive.sdk_client.build")
async def test_upload_chapter_raises_when_store_is_not_initialized(
    _mock_build: MagicMock,
) -> None:
    store = _create_archive_store(GoogleDriveFolderCache())
    store._sdk_client.upload_file = AsyncMock()

    with pytest.raises(ClientNotInitializedError, match="not initialized"):
        await _upload_chapter(store)

    store._sdk_client.upload_file.assert_not_awaited()
