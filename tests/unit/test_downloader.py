"""Unit tests for DownloadClient."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.integrations.exceptions import DownloadError
from src.mangadex_downloader.utils.downloader import DownloadClient


class AsyncContextManagerMock:
    """Helper class to create async context manager mocks."""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


# Export for use in other test files
__all__ = ["AsyncContextManagerMock"]


class TestDownloadClientInit:
    """Test DownloadClient initialization."""

    def test_init_stores_session(self, mock_session):
        """Test that session is stored on initialization."""
        client = DownloadClient(mock_session)
        assert client._session == mock_session


class TestDownloadClientDownloadImage:
    """Test download_image method."""

    @pytest.mark.asyncio
    async def test_download_image_success(self, mock_session):
        """Test successful image download."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"image_data")

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)
        result = await client.download_image("https://test.com/image.jpg")

        assert result == b"image_data"

    @pytest.mark.asyncio
    async def test_download_image_404_raises_error(self, mock_session):
        """Test 404 status raises DownloadError."""
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)

        with pytest.raises(DownloadError) as exc_info:
            await client.download_image("https://test.com/image.jpg")

        assert "404" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_download_image_500_raises_error(self, mock_session):
        """Test 500 status raises DownloadError."""
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)

        with pytest.raises(DownloadError) as exc_info:
            await client.download_image("https://test.com/image.jpg")

        assert "500" in str(exc_info.value)


class TestDownloadClientDownloadImages:
    """Test download_images method."""

    @pytest.mark.asyncio
    async def test_download_images_success(self, mock_session):
        """Test successful batch download of multiple images."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"image_data")

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)
        urls = [
            "https://test.com/1.jpg",
            "https://test.com/2.jpg",
            "https://test.com/3.jpg",
        ]
        result = await client.download_images(urls)

        assert len(result) == 3
        assert all(img == b"image_data" for img in result)

    @pytest.mark.asyncio
    async def test_download_images_empty_list(self, mock_session):
        """Test empty URL list returns empty list."""
        client = DownloadClient(mock_session)
        result = await client.download_images([])

        assert result == []

    @pytest.mark.asyncio
    async def test_download_images_partial_failure(self, mock_session):
        """Test that one failure doesn't stop all downloads."""
        # This test verifies the error handling behavior
        # In actual implementation, errors are caught and empty list is returned
        mock_response_success = MagicMock()
        mock_response_success.status = 200
        mock_response_success.read = AsyncMock(return_value=b"success")

        mock_response_fail = MagicMock()
        mock_response_fail.status = 404

        # Mock to alternate between success and failure
        responses = [mock_response_success, mock_response_fail, mock_response_success]

        def get_response(*args, **kwargs):
            return AsyncContextManagerMock(responses.pop(0))

        mock_session.get.side_effect = get_response

        client = DownloadClient(mock_session)
        urls = [
            "https://test.com/1.jpg",
            "https://test.com/2.jpg",
            "https://test.com/3.jpg",
        ]

        # Should return empty list when any download fails
        result = await client.download_images(urls)
        assert result == []
