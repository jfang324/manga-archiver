from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.integrations.content_providers import MangaDexApiClient
from src.mangadex_downloader.integrations.exceptions import (
    ApiError,
    NotFoundError,
    RateLimitError,
)
from tests.conftest import AsyncContextManagerMock
from tests.unit.integrations.mock_mangadex_api_data import (
    mock_chapter_data,
    mock_download_resource_data,
    mock_empty_chapter_data,
    mock_empty_manga_data,
    mock_malformed_download_resource_data,
    mock_manga_data,
    mock_nested_data,
    mock_processed_chapter_data,
    mock_processed_download_resource_data,
    mock_processed_download_resource_data_saver,
    mock_processed_manga_data,
)


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

    @pytest.mark.parametrize(
        "response_code, expected_error",
        [
            (404, NotFoundError),
            (429, RateLimitError),
            (500, ApiError),
        ],
    )
    async def test_failed_request_raises_custom_errors(
        self, mock_session, response_code, expected_error
    ):
        mock_response = MagicMock()
        mock_response.status = response_code

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client._request("https://test.com")


class TestMangaDexApiClientGetNested:
    @pytest.mark.parametrize(
        "raw_data, keys, expected_result",
        [
            ({"a": {"b": "value"}}, ["a", "b"], "value"),
            (mock_nested_data, ["title", "en"], "Test Title"),
        ],
    )
    def test_existing_keys_returns_value(self, raw_data, keys, expected_result):
        result = MangaDexApiClient._get_nested(raw_data, *keys)

        assert result == expected_result

    @pytest.mark.parametrize(
        "raw_data, keys, default, expected_result",
        [
            ({"a": {}}, ["a", "b"], "default", "default"),
            (mock_nested_data, ["nonexistent"], None, None),
        ],
    )
    def test_missing_keys_returns_default(
        self, raw_data, keys, default, expected_result
    ):
        result = MangaDexApiClient._get_nested(raw_data, *keys, default=default)

        assert result == expected_result


class TestMangaDexApiClientSearchManga:
    @pytest.mark.parametrize(
        "return_value, expected_result",
        [
            (mock_manga_data, mock_processed_manga_data),
            (mock_empty_manga_data, []),
        ],
    )
    async def test_search_manga_success(
        self, mock_session, return_value, expected_result
    ):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=return_value)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.search_manga("test")

        assert len(result) == len(expected_result)
        assert all(result[i] == expected_result[i] for i in range(len(result)))

    @pytest.mark.parametrize(
        "error_code, expected_error",
        [
            (500, ApiError),
            (404, NotFoundError),
            (429, RateLimitError),
        ],
    )
    async def test_search_manga_raises_api_errors(
        self, mock_session, error_code, expected_error
    ):
        mock_response = MagicMock()
        mock_response.status = error_code

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
            await client.search_manga("test")


class TestMangaDexApiClientGetChapters:
    @pytest.mark.parametrize(
        "return_value, expected_result",
        [
            (mock_chapter_data, mock_processed_chapter_data),
            (mock_empty_chapter_data, []),
        ],
    )
    async def test_get_chapters_success(
        self, mock_session, return_value, expected_result
    ):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(return_value=return_value)

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)
        result = await client.get_chapters("1")

        assert len(result) == len(expected_result)
        assert all(result[i] == expected_result[i] for i in range(len(result)))

    @pytest.mark.parametrize(
        "error_code, expected_error",
        [
            (500, ApiError),
            (404, NotFoundError),
            (429, RateLimitError),
        ],
    )
    async def test_get_chapters_raises_api_errors(
        self, mock_session, error_code, expected_error
    ):
        mock_response = MagicMock()
        mock_response.status = error_code

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

        client = MangaDexApiClient(mock_session)

        with pytest.raises(expected_error):
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

    @pytest.mark.parametrize(
        "error_code, expected_error",
        [
            (500, ApiError),
            (404, NotFoundError),
            (429, RateLimitError),
        ],
    )
    async def test_get_download_resource_raises_api_errors(
        self, mock_session, error_code, expected_error
    ):
        mock_response = MagicMock()
        mock_response.status = error_code

        mock_session.get.return_value = AsyncContextManagerMock(mock_response)

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
    )
    def test_process_with_data_saver_param(self, data_saver, raw_data, expected_result):
        client = MangaDexApiClient(MagicMock(), data_saver=data_saver)
        result = client._process_download_resource_data(raw_data)

        assert result == expected_result

    def test_process_fallback_to_standard_when_saver_missing(self):
        client = MangaDexApiClient(MagicMock(), data_saver=True)
        result = client._process_download_resource_data(
            mock_malformed_download_resource_data
        )

        assert result == mock_processed_download_resource_data
