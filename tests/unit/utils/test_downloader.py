from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.integrations.exceptions import (
    BadGatewayError,
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.utils.download_limiter import DownloadLimiter
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
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)
        result = await client.download_image(
            "https://test.com/image.jpg", DownloadLimiter(base_limit=1)
        )

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
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)

        with pytest.raises(expected_error):
            await client.download_image("https://test.com/image.jpg", DownloadLimiter(base_limit=1))


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
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = DownloadClient(mock_session)
        result = await client.download_images(urls, DownloadLimiter(base_limit=1))

        assert len(result) == len(urls)
        assert result == expected_result

    @patch("asyncio.create_task")
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
        self, mock_create_task, mock_session, mock_api_response_list, expect_error, task_tracker
    ) -> None:
        mock_create_task.side_effect = task_tracker
        mock_session.get.side_effect = mock_api_response_list

        client = DownloadClient(mock_session)
        urls = [
            "https://test.com/1.jpg",
            "https://test.com/2.jpg",
            "https://test.com/3.jpg",
        ]

        if expect_error:
            with pytest.raises(expect_error):
                await client.download_images(urls, DownloadLimiter(base_limit=1))

            for task in task_tracker.tasks:
                if not task.done():
                    task.cancel.assert_called_once()
        else:
            results = await client.download_images(urls, DownloadLimiter(base_limit=1))
            assert len(results) == len(urls)


class TestDownloadClientLimiterFeedback:
    async def test_download_with_retry_records_clean_success(self, mock_session) -> None:
        response = MagicMock(status=200, read=AsyncMock(return_value=b"image_data"))
        mock_session.get.return_value = AsyncContextManagerMock(response)
        limiter = MagicMock()
        limiter.acquire.return_value = AsyncContextManagerMock(None)
        limiter.record_success = AsyncMock()
        limiter.record_retryable_error = AsyncMock()

        client = DownloadClient(mock_session)

        result = await client._download_with_retry(
            "https://test.com/image.jpg", headers=None, limiter=limiter
        )

        assert result == b"image_data"
        limiter.record_success.assert_awaited_once_with()
        limiter.record_retryable_error.assert_not_awaited()

    @patch("asyncio.sleep", new_callable=AsyncMock)
    async def test_download_with_retry_does_not_record_success_after_retry(
        self, mock_sleep, mock_session
    ) -> None:
        responses = [
            AsyncContextManagerMock(MagicMock(status=502, read=AsyncMock(return_value=None))),
            AsyncContextManagerMock(MagicMock(status=200, read=AsyncMock(return_value=b"image"))),
        ]
        mock_session.get.side_effect = responses
        limiter = MagicMock()
        limiter.acquire.return_value = AsyncContextManagerMock(None)
        limiter.record_success = AsyncMock()
        limiter.record_retryable_error = AsyncMock()

        client = DownloadClient(mock_session)

        result = await client._download_with_retry(
            "https://test.com/image.jpg", headers=None, limiter=limiter
        )

        assert result == b"image"
        mock_sleep.assert_awaited_once()
        limiter.record_success.assert_not_awaited()
        limiter.record_retryable_error.assert_awaited_once_with()
