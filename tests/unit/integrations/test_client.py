from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.integrations import MangaDexApiClient
from src.mangadex_downloader.integrations.exceptions import (
    ApiError,
    NotFoundError,
    RateLimitError,
)
from tests.conftest import AsyncContextManagerMock
from tests.mock_data import (
    mock_chapter_data,
    mock_download_resource_data,
    mock_download_resource_data_with_saver,
    mock_empty_chapter_data,
    mock_empty_manga_data,
    mock_manga_data,
    mock_nested_data,
    mock_processed_chapter_data,
    mock_processed_download_resource_data,
    mock_processed_download_resource_data_from_saver,
    mock_processed_download_resource_data_saver,
    mock_processed_manga_data,
)


class TestMangaDexApiClientInit:
    def test_init_with_defaults(self, mock_session):
        client = MangaDexApiClient(mock_session)

        assert client._session == mock_session
        assert client._data_saver is False

    def test_init_with_data_saver(self, mock_session):
        client = MangaDexApiClient(mock_session, data_saver=True)

        assert client._session == mock_session
        assert client._data_saver is True


class TestMangaDexApiClientRequest:
    @pytest.mark.asyncio
    async def test_request_success_returns_json(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client._request("https://test.com")

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_request_404_raises_not_found(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(NotFoundError):
            await client._request("https://test.com")

    @pytest.mark.asyncio
    async def test_request_429_raises_rate_limit(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 429

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(RateLimitError):
            await client._request("https://test.com")

    @pytest.mark.asyncio
    async def test_request_other_error_raises_api_error(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(ApiError):
            await client._request("https://test.com")


class TestMangaDexApiClientGetNested:
    def test_get_nested_simple_key(self):
        data = {"a": {"b": "value"}}
        result = MangaDexApiClient._get_nested(data, "a", "b")

        assert result == "value"

    def test_get_nested_with_default(self):
        data = {"a": {}}
        result = MangaDexApiClient._get_nested(data, "a", "b", default="default")

        assert result == "default"

    def test_get_nested_multiple_keys(self):
        result = MangaDexApiClient._get_nested(mock_nested_data, "title", "en")

        assert result == "Test Title"

    def test_get_nested_missing_key_returns_default(self):
        result = MangaDexApiClient._get_nested(mock_nested_data, "nonexistent")

        assert result == ""


class TestMangaDexApiClientSearchManga:
    @pytest.mark.asyncio
    async def test_search_manga_success(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_manga_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.search_manga("test")

        assert len(result) == len(mock_processed_manga_data)
        assert result[0]["title"] == "Attack on Titan"

    @pytest.mark.asyncio
    async def test_search_manga_empty_results(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_empty_manga_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.search_manga("nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_manga_api_error_raises_error(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(ApiError, match="API error"):
            await client.search_manga("test")


class TestMangaDexApiClientGetChapters:
    @pytest.mark.asyncio
    async def test_get_chapters_success(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_chapter_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        # Should be sorted by chapter number
        assert len(result) == len(mock_processed_chapter_data)

    @pytest.mark.asyncio
    async def test_get_chapters_empty(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_empty_chapter_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_chapters_api_error(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(ApiError, match="API error"):
            await client.get_chapters("1")


class TestMangaDexApiClientGetDownloadResource:
    @pytest.mark.asyncio
    async def test_get_download_resource_success(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_download_resource_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_download_resource("1")

        assert result == mock_processed_download_resource_data

    @pytest.mark.asyncio
    async def test_get_download_resource_not_found(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(NotFoundError):
            await client.get_download_resource("1")


class TestMangaDexApiClientProcessDownloadResource:
    def test_process_standard_quality(self):
        client = MangaDexApiClient(MagicMock(), data_saver=False)
        result = client._process_download_resource_data(
            mock_download_resource_data_with_saver
        )

        assert result == mock_processed_download_resource_data_from_saver

    def test_process_data_saver_quality(self):
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(
            mock_download_resource_data_with_saver
        )

        assert result == mock_processed_download_resource_data_saver

    def test_process_fallback_to_standard_when_saver_missing(self):
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(mock_download_resource_data)

        # Should fallback to standard quality
        assert "data/" in result["urls"][0]
