from unittest.mock import MagicMock, patch

import pytest

from src.manga_archiver.integrations.content_providers.allanime.client import AllMangaClient
from src.manga_archiver.integrations.content_providers.allanime.constants import CDN_BASE_URL
from src.manga_archiver.integrations.exceptions import (
    ApiError,
    BadGatewayError,
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.models import ContentSource
from tests.conftest import AsyncContextManagerMock
from tests.unit.integrations.content_providers.allanime.mock_allanime_api_data import (
    mock_chapter_pages_missing_urls,
    mock_chapter_pages_response,
    mock_chapter_response_empty_pages,
    mock_chapter_response_no_edges,
    mock_manga_details_empty_chapters,
    mock_manga_details_empty_strings,
    mock_manga_details_response,
    mock_manga_details_unsorted_chapters,
    mock_processed_chapters,
    mock_processed_download_resource,
    mock_processed_search_results,
    mock_search_response,
    mock_search_response_empty,
    mock_search_response_missing_ids,
    mock_search_response_no_english_name,
)


class TestAllMangaClientRequest:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [((200, {"data": "test"}), {"data": "test"})],
        indirect=["mock_api_response"],
    )
    async def test_request_success_returns_json(
        self, mock_session, mock_api_response, expected_result
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = AllMangaClient(mock_session)
        result = await client._request("https://test.com")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), ApiError),
            ((502, {}), BadGatewayError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error", "bad_gateway"],
    )
    async def test_failed_request_raises_custom_errors(
        self, mock_session, mock_api_response, expected_error
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = AllMangaClient(mock_session)

        with pytest.raises(expected_error):
            await client._request("https://test.com")


class TestAllMangaClientSearchManga:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [
            ((200, mock_search_response), mock_processed_search_results),
            ((200, mock_search_response_empty), []),
        ],
        indirect=["mock_api_response"],
        ids=["full_response", "empty_response"],
    )
    async def test_search_manga_success(
        self, mock_session, mock_api_response, expected_result
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = AllMangaClient(mock_session)
        result = await client.search_manga("jujutsu", 1, 20)

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_search_response_no_english_name)],
        indirect=["mock_api_response"],
    )
    async def test_search_manga_prefers_english_name(self, mock_session, mock_api_response) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.search_manga("test", 1, 20)
        assert len(result) == 1
        assert result[0].title == "Native Name Only"

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_search_response_missing_ids)],
        indirect=["mock_api_response"],
    )
    async def test_search_manga_filters_missing_ids(self, mock_session, mock_api_response) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.search_manga("test", 1, 20)

        assert len(result) == 1
        assert result[0].id == "valid"


class TestAllMangaClientGetChapters:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [((200, mock_manga_details_response), mock_processed_chapters)],
        indirect=["mock_api_response"],
        ids=["full_response"],
    )
    async def test_get_chapters_success(
        self, mock_session, mock_api_response, expected_result
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)

        client = AllMangaClient(mock_session)
        result = await client.get_chapters("PBouNk6dWWBuswfX7")

        assert result == expected_result

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_manga_details_empty_chapters)],
        indirect=["mock_api_response"],
    )
    async def test_get_chapters_empty_returns_empty_list(
        self, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        result = await client.get_chapters("empty123")
        assert result == []

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_manga_details_unsorted_chapters)],
        indirect=["mock_api_response"],
    )
    async def test_get_chapters_sorts_by_chapter_num(self, mock_session, mock_api_response) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.get_chapters("test")

        assert len(result) == 4
        assert result[0].chapter_num == 1.0
        assert result[1].chapter_num == 2.0
        assert result[2].chapter_num == 2.5
        assert result[3].chapter_num == 10.0

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_manga_details_empty_strings)],
        indirect=["mock_api_response"],
    )
    async def test_get_chapters_skips_empty_strings(self, mock_session, mock_api_response) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.get_chapters("test")

        assert len(result) == 2

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), ApiError),
            ((502, {}), BadGatewayError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error", "bad_gateway"],
    )
    async def test_get_chapters_raises_api_errors(
        self, mock_session, mock_api_response, expected_error
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        with pytest.raises(expected_error):
            await client.get_chapters("test")


class TestAllMangaClientGetDownloadResource:
    @pytest.mark.parametrize(
        "mock_api_response, expected_result",
        [((200, mock_chapter_pages_response), mock_processed_download_resource)],
        indirect=["mock_api_response"],
        ids=["full_response"],
    )
    async def test_get_download_resource_success(
        self, mock_session, mock_api_response, expected_result
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.get_download_resource("PBouNk6dWWBuswfX7:25")

        assert result == expected_result
        assert result.source == ContentSource.ALLMANGA

    async def test_get_download_resource_invalid_chapter_id_format(self) -> None:
        client = AllMangaClient(MagicMock())

        with pytest.raises(ValueError):
            await client.get_download_resource("invalid-id-without-colon")

    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), ApiError),
            ((502, {}), BadGatewayError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error", "bad_gateway"],
    )
    async def test_get_download_resource_raises_api_errors(
        self, mock_session, mock_api_response, expected_error
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        with pytest.raises(expected_error):
            await client.get_download_resource("test:1")

    @pytest.mark.parametrize(
        "mock_api_response",
        [
            (200, mock_chapter_response_empty_pages),
            (200, mock_chapter_response_no_edges),
        ],
        indirect=["mock_api_response"],
        ids=["empty_pages", "no_edges"],
    )
    async def test_get_download_resource_raises_api_error_when_no_pages(
        self, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        with pytest.raises(ApiError):
            await client.get_download_resource("test:1")

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_chapter_pages_response)],
        indirect=["mock_api_response"],
    )
    async def test_get_download_resource_builds_full_urls(
        self, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        result = await client.get_download_resource("manga:1")

        assert len(result.urls) == 2
        assert result.urls[0] == f"{CDN_BASE_URL}images/test/chapter/sub_123/1.png"
        assert result.urls[1] == f"{CDN_BASE_URL}images/test/chapter/sub_123/2.png"

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_chapter_pages_missing_urls)],
        indirect=["mock_api_response"],
    )
    async def test_get_download_resource_skips_missing_urls(
        self, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        with pytest.raises(ApiError):
            await client.get_download_resource("manga:1")

    @patch("src.manga_archiver.integrations.content_providers.allanime.client.decode_tobeparsed")
    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, {"data": {"tobeparsed": "encrypted_data_string"}})],
        indirect=["mock_api_response"],
    )
    async def test_get_download_resource_decrypts_tobeparsed(
        self, mock_decode: MagicMock, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        mock_decode.return_value = {
            "chapterPages": {"edges": [{"pictureUrls": [{"url": "decoded.jpg"}]}]}
        }
        client = AllMangaClient(mock_session)
        result = await client.get_download_resource("manga:1")

        mock_decode.assert_called_once_with("encrypted_data_string")
        assert len(result.urls) == 1
        assert result.urls[0] == f"{CDN_BASE_URL}decoded.jpg"


class TestAllMangaClientErrorPropagation:
    @pytest.mark.parametrize(
        "method_name,method_args",
        [
            ("search_manga", ("query", 1, 20)),
            ("get_chapters", ("manga_id",)),
            ("get_download_resource", ("manga:1",)),
        ],
    )
    @pytest.mark.parametrize(
        "mock_api_response, expected_error",
        [
            ((404, {}), NotFoundError),
            ((429, {}), RateLimitError),
            ((500, {}), ApiError),
            ((502, {}), BadGatewayError),
        ],
        indirect=["mock_api_response"],
        ids=["not_found", "rate_limit", "server_error", "bad_gateway"],
    )
    async def test_error_propagates(
        self, mock_session, mock_api_response, method_name, method_args, expected_error
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        method = getattr(client, method_name)

        with pytest.raises(expected_error):
            await method(*method_args)
