import asyncio
from collections.abc import Callable, Generator
from unittest.mock import MagicMock, patch

import pytest

from src.manga_archiver.integrations.storage_providers.google_drive.client import GoogleDriveClient
from src.manga_archiver.integrations.storage_providers.google_drive.constants import (
    ROOT_FOLDER_NAME,
)
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleApiStoredToken,
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


@pytest.fixture
def google_drive_client_factory() -> Generator[Callable[[], GoogleDriveClient], None, None]:
    with patch("src.manga_archiver.integrations.storage_providers.google_drive.client.build"):
        yield lambda: GoogleDriveClient(_token())


def test_initialize_cache_is_visible_to_other_client_instance(
    google_drive_client_factory: Callable[[], GoogleDriveClient],
) -> None:
    first_client = google_drive_client_factory()
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
    second_client = google_drive_client_factory()

    assert init_result.root_folder_id == "root_123"
    assert init_result.cached_folder_count == 1
    assert second_client.get_manga_folder_id("Test Manga", "mangadex") == "folder_123"


@pytest.mark.asyncio
async def test_get_or_create_manga_folder_caches_search_result(
    google_drive_client_factory: Callable[[], GoogleDriveClient],
) -> None:
    GoogleDriveClient._root_folder_id = "root_123"
    client = google_drive_client_factory()
    client._search_folder_by_name = MagicMock(return_value="folder_123")
    client._create_folder_sync = MagicMock()

    first_folder_id = await client.get_or_create_manga_folder("Test Manga", "mangadex")
    second_folder_id = await client.get_or_create_manga_folder("Test Manga", "mangadex")

    assert first_folder_id == "folder_123"
    assert second_folder_id == "folder_123"
    client._search_folder_by_name.assert_called_once_with("Test Manga", "root_123", "mangadex")
    client._create_folder_sync.assert_not_called()


@pytest.mark.asyncio
async def test_concurrent_get_or_create_manga_folder_creates_one_folder(
    google_drive_client_factory: Callable[[], GoogleDriveClient],
) -> None:
    GoogleDriveClient._root_folder_id = "root_123"
    client = google_drive_client_factory()
    client._search_folder_by_name = MagicMock(return_value=None)
    client._create_folder_sync = MagicMock(return_value="folder_123")

    results = await asyncio.gather(
        client.get_or_create_manga_folder("Test Manga", "mangadex"),
        client.get_or_create_manga_folder("Test Manga", "mangadex"),
    )

    assert results == ["folder_123", "folder_123"]
    client._search_folder_by_name.assert_called_once_with("Test Manga", "root_123", "mangadex")
    client._create_folder_sync.assert_called_once()
