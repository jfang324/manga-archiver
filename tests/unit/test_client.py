"""Unit tests for MangaDexApiClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.integrations import MangaDexApiClient
from src.mangadex_downloader.integrations.exceptions import (
    ApiError,
    NotFoundError,
    RateLimitError,
)
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


class AsyncContextManagerMock:
    """Helper class to create async context manager mocks."""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


class TestMangaDexApiClientInit:
    """Test MangaDexApiClient initialization."""

    def test_init_with_defaults(self, mock_session):
        """Test initialization with default parameters."""
        client = MangaDexApiClient(mock_session)
        assert client._session == mock_session
        assert client._data_saver is False

    def test_init_with_data_saver(self, mock_session):
        """Test initialization with data_saver enabled."""
        client = MangaDexApiClient(mock_session, data_saver=True)
        assert client._session == mock_session
        assert client._data_saver is True


class TestMangaDexApiClientRequest:
    """Test _request method."""

    @pytest.mark.asyncio
    async def test_request_success_returns_json(self, mock_session):
        """Test successful request returns JSON data."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value={"data": "test"})

        # Make session.get return an async context manager
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client._request("https://test.com")

        assert result == {"data": "test"}

    @pytest.mark.asyncio
    async def test_request_404_raises_not_found(self, mock_session):
        """Test 404 status raises NotFoundError."""
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(NotFoundError):
            await client._request("https://test.com")

    @pytest.mark.asyncio
    async def test_request_429_raises_rate_limit(self, mock_session):
        """Test 429 status raises RateLimitError."""
        mock_response = MagicMock()
        mock_response.status = 429

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(RateLimitError):
            await client._request("https://test.com")

    @pytest.mark.asyncio
    async def test_request_other_error_raises_api_error(self, mock_session):
        """Test other error statuses raise ApiError."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(ApiError):
            await client._request("https://test.com")


class TestMangaDexApiClientGetNested:
    """Test _get_nested static method."""

    def test_get_nested_simple_key(self):
        """Test getting value with simple key path."""
        data = {"a": {"b": "value"}}
        result = MangaDexApiClient._get_nested(data, "a", "b")
        assert result == "value"

    def test_get_nested_with_default(self):
        """Test default value when key not found."""
        data = {"a": {}}
        result = MangaDexApiClient._get_nested(data, "a", "b", default="default")
        assert result == "default"

    def test_get_nested_multiple_keys(self):
        """Test getting deeply nested value."""
        result = MangaDexApiClient._get_nested(mock_nested_data, "title", "en")
        assert result == "Test Title"

    def test_get_nested_missing_key_returns_default(self):
        """Test missing key returns empty default."""
        result = MangaDexApiClient._get_nested(mock_nested_data, "nonexistent")
        assert result == ""


class TestMangaDexApiClientSearchManga:
    """Test search_manga method."""

    @pytest.mark.asyncio
    async def test_search_manga_success(self, mock_session):
        """Test successful manga search returns processed manga list."""
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
        """Test empty search results."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_empty_manga_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.search_manga("nonexistent")

        assert result == []

    @pytest.mark.asyncio
    async def test_search_manga_api_error_raises_error(self, mock_session):
        """Test API error returns empty list."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(ApiError, match="API error"):
            await client.search_manga("test")


class TestMangaDexApiClientGetChapters:
    """Test get_chapters method."""

    @pytest.mark.asyncio
    async def test_get_chapters_success(self, mock_session):
        """Test successful chapter retrieval."""
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
        """Test empty chapter list."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_empty_chapter_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        assert result == []

    @pytest.mark.asyncio
    async def test_get_chapters_api_error(self, mock_session):
        """Test API error returns empty list."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        assert result == []


class TestMangaDexApiClientGetDownloadResource:
    """Test get_download_resource method."""

    @pytest.mark.asyncio
    async def test_get_download_resource_success(self, mock_session):
        """Test successful download resource retrieval."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=mock_download_resource_data)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_download_resource("1")

        assert result == mock_processed_download_resource_data

    @pytest.mark.asyncio
    async def test_get_download_resource_not_found(self, mock_session):
        """Test 404 raises NotFoundError."""
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(NotFoundError):
            await client.get_download_resource("1")


class TestMangaDexApiClientProcessDownloadResource:
    """Test _process_download_resource_data method."""

    def test_process_standard_quality(self):
        """Test processing with standard quality (data)."""
        client = MangaDexApiClient(MagicMock(), data_saver=False)
        result = client._process_download_resource_data(
            mock_download_resource_data_with_saver
        )

        assert result == mock_processed_download_resource_data_from_saver

    def test_process_data_saver_quality(self):
        """Test processing with data-saver quality."""
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(
            mock_download_resource_data_with_saver
        )

        assert result == mock_processed_download_resource_data_saver

    def test_process_fallback_to_standard_when_saver_missing(self):
        """Test fallback to standard quality when data-saver not available."""
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(mock_download_resource_data)

        # Should fallback to standard quality
        assert "data/" in result["urls"][0]
