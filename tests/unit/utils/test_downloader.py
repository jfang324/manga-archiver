import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mangadex_downloader.integrations.exceptions import DownloadError
from src.mangadex_downloader.utils.downloader import DownloadClient
from tests.conftest import AsyncContextManagerMock


class TestDownloadClientInit:
    def test_init_stores_session(self, mock_session):
        client = DownloadClient(mock_session)

        assert client._session == mock_session


class TestDownloadClientDownloadImage:
    @pytest.mark.asyncio
    async def test_download_image_success(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.read = AsyncMock(return_value=b"image_data")

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)
        result = await client.download_image("https://test.com/image.jpg")

        assert result == b"image_data"

    @pytest.mark.asyncio
    async def test_download_image_404_raises_error(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 404

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)

        with pytest.raises(DownloadError, match="404"):
            await client.download_image("https://test.com/image.jpg")

    @pytest.mark.asyncio
    async def test_download_image_500_raises_error(self, mock_session):
        mock_response = MagicMock()
        mock_response.status = 500

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = DownloadClient(mock_session)

        with pytest.raises(DownloadError, match="500"):
            await client.download_image("https://test.com/image.jpg")


class TestDownloadClientDownloadImages:
    @pytest.mark.asyncio
    async def test_download_images_success(self, mock_session):
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
        client = DownloadClient(mock_session)
        result = await client.download_images([])

        assert result == []

    @pytest.mark.asyncio
    async def test_download_images_partial_failure(self, mock_session):
        mock_response_success = MagicMock()
        mock_response_success.status = 200
        mock_response_success.read = AsyncMock(return_value=b"success")

        mock_response_fail = MagicMock()
        mock_response_fail.status = 404

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

        tasks_created = []

        original_create_task = asyncio.create_task

        def fake_create_task(coro):
            task = original_create_task(coro)
            task.cancel = MagicMock(wraps=task.cancel)
            tasks_created.append(task)
            return task

        with patch(
            "asyncio.create_task", side_effect=fake_create_task
        ) and pytest.raises(DownloadError, match="404"):
            await client.download_images(urls)

        for task in tasks_created:
            if not task.done():
                task.cancel.assert_called_once()
