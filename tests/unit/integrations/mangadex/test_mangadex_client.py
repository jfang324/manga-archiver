from unittest.mock import MagicMock

import pytest

from src.manga_archiver.integrations.content_providers.mangadex import MangaDexApiClient
from src.manga_archiver.integrations.exceptions import (
    ApiError,
    NotFoundError,
    RateLimitError,
)
from tests.conftest import (
    AsyncContextManagerMock,
)
from tests.unit.integrations.mangadex.mock_mangadex_api_data import (
    mock_chapter_data,
    mock_download_resource_data,
    mock_empty_chapter_data,
    mock_empty_manga_data,
    mock_malformed_download_resource_data,
    mock_manga_data,
    mock_processed_chapter_data,
    mock_processed_download_resource_data,
    mock_processed_download_resource_data_saver,
    mock_processed_manga_data,
)


class TestMangaDexApiClientRequest:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [
            ((200, {"data": "test"}), {"data": "test"}),
        ],
        indirect=["mock_api_response"],
    )
    async def test_request_success_returns_json(
        self, mock_session, mock_api_response, expected_result
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)
        result = await client._request("https://test.com")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), ApiError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error"],
    )
    async def test_failed_request_raises_custom_errors(
        self, mock_session, mock_api_response, expected_error
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client._request("https://test.com")


class TestMangaDexApiClientSearchManga:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [
            ((200, mock_manga_data), mock_processed_manga_data),
            ((200, mock_empty_manga_data), []),
        ],
        indirect=["mock_api_response"],
        ids=["full_response", "empty_response"],
    )
    async def test_search_manga_success(self, mock_session, mock_api_response, expected_result):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)
        result = await client.search_manga("test", 1, 10)

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((500, {}), ApiError),
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
        ],
        indirect=["mock_api_response"],
        ids=["server_error", "not_found", "rate_limit"],
    )
    async def test_search_manga_raises_api_errors(
        self, mock_session, mock_api_response, expected_error
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client.search_manga("test", 1, 10)


class TestMangaDexApiClientGetChapters:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [
            ((200, mock_chapter_data), mock_processed_chapter_data),
            ((200, mock_empty_chapter_data), []),
        ],
        indirect=["mock_api_response"],
        ids=["full_response", "empty_response"],
    )
    async def test_get_chapters_success(self, mock_session, mock_api_response, expected_result):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((500, {}), ApiError),
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
        ],
        indirect=["mock_api_response"],
        ids=["server_error", "not_found", "rate_limit"],
    )
    async def test_get_chapters_raises_api_errors(
        self, mock_session, mock_api_response, expected_error
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client.get_chapters("1")


class TestMangaDexApiClientGetDownloadResource:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [
            ((200, mock_download_resource_data), mock_processed_download_resource_data),
            (
                (200, mock_malformed_download_resource_data),
                mock_processed_download_resource_data,
            ),
        ],
        indirect=["mock_api_response"],
        ids=["full_response", "malformed_response"],
    )
    async def test_get_download_resource_success(
        self, mock_session, mock_api_response, expected_result
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_download_resource("1")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((500, {}), ApiError),
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
        ],
        indirect=["mock_api_response"],
        ids=["server_error", "not_found", "rate_limit"],
    )
    async def test_get_download_resource_raises_api_errors(
        self, mock_session, mock_api_response, expected_error
    ):
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client.get_download_resource("1")


class TestMangaDexApiClientProcessDownloadResource:
    @pytest.mark.parametrize(
        "data_saver, raw_data, expected_result",
        [
            (
                False,
                mock_download_resource_data,
                mock_processed_download_resource_data,
            ),
            (
                True,
                mock_download_resource_data,
                mock_processed_download_resource_data_saver,
            ),
        ],
        ids=["no_data_saver", "data_saver"],
    )
    def test_process_with_data_saver_param(self, data_saver, raw_data, expected_result):
        client = MangaDexApiClient(MagicMock(), data_saver=data_saver)
        result = client._process_download_resource_data(raw_data)

        assert result == expected_result

    def test_process_fallback_to_standard_when_saver_missing(self):
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(mock_malformed_download_resource_data)

        assert result == mock_processed_download_resource_data
