import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.integrations.content_providers.allanime.client import AllMangaClient
from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_LANES,
    CDN_BASE_URL,
    CHAPTER_HASH,
    CHAPTER_PAGES_LANE,
    PERSISTED_QUERY_HASH_FALLBACKS,
    PERSISTED_QUERY_NOT_FOUND,
)
from src.manga_archiver.integrations.content_providers.allanime.keygen import AllAnimeKeygen
from src.manga_archiver.integrations.exceptions import (
    ApiError,
    BadGatewayError,
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.models import ContentSource
from tests.conftest import AsyncContextManagerMock
from tests.unit.integrations.content_providers.allanime.conftest import fallback_keygen
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

    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, mock_chapter_pages_response)],
        indirect=["mock_api_response"],
    )
    async def test_get_download_resource_sends_build_id_and_lane(
        self, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)
        await client.get_download_resource("manga:1")

        call_kwargs = mock_session.get.call_args.kwargs
        assert call_kwargs["headers"]["x-build-id"] == ALLANIME_FALLBACK_BUILD_ID
        extensions = json.loads(call_kwargs["params"]["extensions"])
        assert extensions["persistedQuery"]["sha256Hash"] == CHAPTER_HASH
        assert extensions["k"] == CHAPTER_PAGES_LANE

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

        mock_decode.assert_called_once_with(
            "encrypted_data_string",
            CHAPTER_PAGES_LANE,
            fallback_keygen(query_hashes=dict(PERSISTED_QUERY_HASH_FALLBACKS)),
        )
        assert len(result.urls) == 1
        assert result.urls[0] == f"{CDN_BASE_URL}decoded.jpg"

    async def test_keygen_failure_raises_api_error(self, mock_session) -> None:
        client = AllMangaClient(mock_session)
        with patch.object(
            client._keygen, "build_aa_req", side_effect=ValueError("Invalid keygen key for lane k9")
        ):
            with pytest.raises(ApiError, match="Failed to generate aaReq token"):
                await client.get_download_resource("manga:1")

    @patch(
        "src.manga_archiver.integrations.content_providers.allanime.client.decode_tobeparsed",
        side_effect=ValueError("encrypted with unknown key"),
    )
    @pytest.mark.parametrize(
        "mock_api_response",
        [(200, {"data": {"tobeparsed": "encrypted_data_string"}})],
        indirect=["mock_api_response"],
    )
    async def test_decode_failure_invalidates_cache_and_raises_api_error(
        self, _mock_decode: MagicMock, mock_session, mock_api_response
    ) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(mock_api_response)
        client = AllMangaClient(mock_session)

        with pytest.raises(ApiError, match="encrypted with unknown key"):
            await client.get_download_resource("manga:1")
        assert client._keygen._cache is None


def _json_response(payload: dict) -> MagicMock:
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value=payload)
    return response


class TestAllMangaClientStaleCrypto:
    async def test_stale_crypto_invalidates_and_raises_rate_limit(self, mock_session) -> None:
        stale = _json_response({"errors": [{"message": "AA_CRYPTO_STALE"}]})
        mock_session.get.return_value = AsyncContextManagerMock(stale)
        client = AllMangaClient(mock_session)

        with pytest.raises(RateLimitError):
            await client.get_download_resource("manga:1")
        assert mock_session.get.call_count == 1
        # The known-stale values must not remain cached for the rest of the TTL
        assert client._keygen._cache is None

    async def test_stale_crypto_failure_triggers_refresh_on_next_call(self, mock_session) -> None:
        stale = _json_response({"errors": [{"message": "AA_CRYPTO_STALE"}]})
        mock_session.get.return_value = AsyncContextManagerMock(stale)
        client = AllMangaClient(mock_session)
        with pytest.raises(RateLimitError):
            await client.get_download_resource("manga:1")
        assert client._keygen._cache is None

        # With the cache emptied by the stale failure, the next token build
        # must re-fetch keygen instead of serving cached values.
        fetched = {
            "build_id": ALLANIME_FALLBACK_BUILD_ID,
            "epoch": 2953,
            "lanes": dict(ALLANIME_FALLBACK_LANES),
        }
        with patch.object(
            client._keygen,
            "_fetch",
            new=AsyncMock(return_value=AllAnimeKeygen.from_dict(fetched)),
        ) as mock_fetch:
            await client._keygen.get()
            mock_fetch.assert_awaited_once()

    async def test_non_dict_error_entries_raise_api_error(self, mock_session) -> None:
        response = _json_response({"errors": ["AA_CRYPTO_STALE"]})
        mock_session.get.return_value = AsyncContextManagerMock(response)
        client = AllMangaClient(mock_session)

        with pytest.raises(ApiError):
            await client.get_download_resource("manga:1")
        assert mock_session.get.call_count == 1

    async def test_rotation_marker_in_later_error_invalidates_and_raises(
        self, mock_session
    ) -> None:
        response = _json_response(
            {"errors": [{"message": "Something else"}, {"message": "AA_CRYPTO_STALE"}]}
        )
        mock_session.get.return_value = AsyncContextManagerMock(response)
        client = AllMangaClient(mock_session)

        with pytest.raises(RateLimitError):
            await client.get_download_resource("manga:1")
        assert mock_session.get.call_count == 1
        assert client._keygen._cache is None


class TestAllMangaClientQueryNotFound:
    def _not_found(self) -> MagicMock:
        return _json_response({"errors": [{"message": PERSISTED_QUERY_NOT_FOUND}]})

    async def test_download_invalidates_and_raises_on_not_found(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(self._not_found())
        client = AllMangaClient(mock_session)

        with pytest.raises(RateLimitError):
            await client.get_download_resource("manga:1")
        assert mock_session.get.call_count == 1
        assert client._keygen._cache is None

    async def test_search_invalidates_and_raises_on_not_found(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(self._not_found())
        client = AllMangaClient(mock_session)

        with pytest.raises(RateLimitError):
            await client.search_manga("jujutsu", 1, 20)
        assert mock_session.get.call_count == 1
        assert client._keygen._cache is None


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
