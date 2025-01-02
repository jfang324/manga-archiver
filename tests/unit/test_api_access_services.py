import pytest
import aiohttp
from unittest.mock import AsyncMock, MagicMock, patch
from src.mangadex_downloader.services.api_access_service import *
from tests.mock_data import *


def create_mock_response(
    status: int, json_data: dict, bytes_data: bytes = b"dummy bytes"
) -> AsyncMock:
    mock_response: AsyncMock = AsyncMock()
    mock_response.status = status
    mock_response.json = AsyncMock(return_value=json_data)
    mock_response.read = AsyncMock(return_value=bytes_data)

    return mock_response


def create_mock_session(mock_response: AsyncMock) -> aiohttp.ClientSession:
    mock_session = MagicMock()

    if mock_response:
        mock_session.get.return_value.__aenter__.return_value = mock_response
        mock_session.get.return_value.__aexit__.return_value = AsyncMock()
    else:
        mock_session.get.return_value.__aenter__.side_effect = Exception(
            "No response from API"
        )

    return mock_session


class TestFetch:
    async def test_fetch_success_returns_json(self):
        mock_response: AsyncMock = create_mock_response(200, mock_manga_data)
        mock_session: aiohttp.ClientSession = create_mock_session(mock_response)
        response: dict = await fetch(mock_session, mock_url)

        assert response == mock_manga_data

    async def test_fetch_failure_returns_none(self):
        mock_response: AsyncMock = create_mock_response(400, {})
        mock_session: aiohttp.ClientSession = create_mock_session(mock_response)
        response: dict = await fetch(mock_session, mock_url)

        assert response is None

    async def test_fetch_no_response_raises_exception(self):
        mock_session: aiohttp.ClientSession = create_mock_session(None)

        with pytest.raises(Exception) as e:
            await fetch(mock_session, mock_url)


class TestRetrieveMangas:
    dummy_session: aiohttp.ClientSession = create_mock_session(
        create_mock_response(200, "dummy data")
    )

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        return_value=mock_manga_data,
    )
    async def test_retrieve_mangas_success_returns_json(self, mock_fetch: AsyncMock):
        response: dict = await retrieve_mangas(self.dummy_session, mock_query)

        assert response == mock_manga_data
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"?title={mock_query}")

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        side_effect=Exception("Error fetching url"),
    )
    async def test_retrieve_mangas_failure_returns_none(self, mock_fetch: AsyncMock):
        response: dict = await retrieve_mangas(self.dummy_session, mock_query)

        assert response is None
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"?title={mock_query}")


class TestRetrieveChapters:
    dummy_session: aiohttp.ClientSession = create_mock_session(
        create_mock_response(200, "dummy data")
    )

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        return_value=mock_chapter_data,
    )
    async def test_retrieve_chapters_success_returns_json(self, mock_fetch: AsyncMock):
        response: dict = await retrieve_chapters(self.dummy_session, mock_manga_id)

        assert response == mock_chapter_data
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"/{mock_manga_id}/feed")

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        side_effect=Exception("Error fetching url"),
    )
    async def test_retrieve_chapters_failure_returns_none(self, mock_fetch: AsyncMock):
        response: dict = await retrieve_chapters(self.dummy_session, mock_manga_id)

        assert response is None
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"/{mock_manga_id}/feed")


class TestRetrieveDownloadResources:
    dummy_session: aiohttp.ClientSession = create_mock_session(
        create_mock_response(200, "dummy data")
    )

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        return_value=mock_download_resource_data,
    )
    async def test_retrieve_download_resources_success_returns_json(
        self, mock_fetch: AsyncMock
    ):
        response: dict = await retrieve_download_resources(
            self.dummy_session, mock_chapter_id
        )

        assert response == mock_download_resource_data
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"/{mock_chapter_id}")

    @patch(
        "src.mangadex_downloader.services.api_access_service.fetch",
        side_effect=Exception("Error fetching url"),
    )
    async def test_retrieve_download_resources_failure_returns_none(
        self, mock_fetch: AsyncMock
    ):
        response: dict = await retrieve_download_resources(
            self.dummy_session, mock_chapter_id
        )

        assert response is None
        assert mock_fetch.call_count == 1
        assert mock_fetch.call_args[0][0] == self.dummy_session
        assert mock_fetch.call_args[0][1].endswith(f"/{mock_chapter_id}")


class TestRetrieveImageData:
    async def test_retrieve_image_data_success_returns_bytes(self):
        mock_response: AsyncMock = create_mock_response(
            200, mock_manga_data, mock_image_data
        )
        mock_session: aiohttp.ClientSession = create_mock_session(mock_response)
        response: bytes = await retrieve_image_data(mock_session, mock_url)

        assert response == mock_image_data

    async def test_retrieve_image_data_failure_returns_none(self):
        mock_response: AsyncMock = create_mock_response(400, {})
        mock_session: aiohttp.ClientSession = create_mock_session(mock_response)
        response: bytes = await retrieve_image_data(mock_session, mock_url)

        assert response is None

    async def test_retrieve_image_data_no_response_returns_none(self):
        mock_session: aiohttp.ClientSession = create_mock_session(None)

        with pytest.raises(Exception) as e:
            response: bytes = await retrieve_image_data(mock_session, mock_url)

            assert response is None
