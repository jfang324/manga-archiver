from unittest.mock import patch

import pytest

from src.manga_archiver.integrations.exceptions import (
    BadGatewayError,
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.utils.downloader import DownloadClient, DownloadError
from tests.conftest import AsyncContextManagerMock


class TestDownloadClientDownloadImage:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [((200, b"image_data"), b"image_data")],
        indirect=["mock_api_response"],
    )
    async def test_download_image_success_returns_bytes(
        self, mock_session, mock_api_response, expected_result
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)
        result = await client.download_image("https://test.com/image.jpg")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), DownloadError),
            ((502, {}), BadGatewayError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error", "bad_gateway"],
    )
    async def test_failed_download_raises_error(
        self, mock_session, mock_api_response, expected_error
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)

        with pytest.raises(expected_error):
            await client.download_image("https://test.com/image.jpg")


class TestDownloadClientDownloadImages:
    @pytest.mark.parametrize(
        "mock_api_response, urls, expected_result",
        [
            (
                (200, b"image_data"),
                ["https://test.com/1.jpg", "https://test.com/2.jpg"],
                [b"image_data", b"image_data"],
            ),
            ((200, b"image_data"), [], []),
        ],
        indirect=["mock_api_response"],
        ids=["multiple_images", "no_images"],
    )
    async def test_download_images_success_returns_bytes(
        self, mock_session, mock_api_response, urls, expected_result
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)
        result = await client.download_images(urls)

        assert len(result) == len(urls)
        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response_list, expect_error",
        [
            ([(200, b"success"), (404, None), (200, b"success")], NotFoundError),
            ([(200, b"image1"), (200, b"image2"), (200, b"image3")], False),
            ([(404, None), (404, None), (404, None)], NotFoundError),
            ([(500, None), (500, None), (500, None)], DownloadError),
        ],
        indirect=["mock_api_response_list"],
        ids=["partial_failure", "all_success", "all_not_found", "all_server_error"],
    )
    async def test_download_images_various_results(
        self, mock_session, mock_api_response_list, expect_error, task_tracker
    ):
        mock_session.get.side_effect = mock_api_response_list

        client = DownloadClient(mock_session)
        urls = [
            "https://test.com/1.jpg",
            "https://test.com/2.jpg",
            "https://test.com/3.jpg",
        ]

        if expect_error:
            with patch("asyncio.create_task", side_effect=task_tracker) and pytest.raises(
                expect_error
            ):
                await client.download_images(urls)

            for task in task_tracker.tasks:
                if not task.done():
                    task.cancel.assert_called_once()
        else:
            with patch("asyncio.create_task", side_effect=task_tracker):
                results = await client.download_images(urls)
                assert len(results) == len(urls)
