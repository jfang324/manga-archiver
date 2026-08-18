import asyncio
import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
    CHAPTER_HASH,
    CRYPTO_TTL_SECONDS,
    MANGA_HASH,
    SEARCH_HASH,
    PersistedQueryName,
)
from src.manga_archiver.integrations.content_providers.allanime.keygen import (
    AllAnimeKeygen,
    KeygenService,
)
from tests.conftest import AsyncContextManagerMock
from tests.unit.integrations.content_providers.allanime.conftest import (
    aareq_key,
    fallback_keygen,
)

# Captured at import time, before the autouse stub_crypto fixture patches it
_real_fetch = KeygenService._fetch


class TestFetchKeygen:
    def _mock_response(self, *, status: int = 200, text: str = "") -> MagicMock:
        response = MagicMock()
        response.status = status
        response.text = AsyncMock(return_value=text)
        return response

    def _valid_keygen_data(self) -> dict:
        return {
            "build_id": ALLANIME_FALLBACK_BUILD_ID,
            "epoch": ALLANIME_FALLBACK_EPOCH,
            "lanes": dict(ALLANIME_FALLBACK_LANES),
            "query_hashes": {},
        }

    async def test_success_returns_validated_keygen(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text=json.dumps(self._valid_keygen_data()))
        )
        service = KeygenService(mock_session)

        keygen = await _real_fetch(service)

        assert keygen == AllAnimeKeygen.from_dict(self._valid_keygen_data())

    async def test_non_200_status_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(self._mock_response(status=500))
        service = KeygenService(mock_session)

        assert await _real_fetch(service) is None

    async def test_client_error_returns_none(self, mock_session) -> None:
        mock_session.get.side_effect = aiohttp.ClientError("connection refused")
        service = KeygenService(mock_session)

        assert await _real_fetch(service) is None

    async def test_timeout_returns_none(self, mock_session) -> None:
        mock_session.get.side_effect = asyncio.TimeoutError
        service = KeygenService(mock_session)

        assert await _real_fetch(service) is None

    async def test_json_decode_error_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text="not-json")
        )
        service = KeygenService(mock_session)

        assert await _real_fetch(service) is None

    async def test_malformed_keygen_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text=json.dumps({"bad": "data"}))
        )
        service = KeygenService(mock_session)

        assert await _real_fetch(service) is None

    async def test_unexpected_exception_propagates(self, mock_session) -> None:
        mock_session.get.side_effect = RuntimeError("unexpected")
        service = KeygenService(mock_session)

        with pytest.raises(RuntimeError, match="unexpected"):
            await _real_fetch(service)


class TestBuildAaReq:
    async def test_token_round_trips_with_keygen_key(self, mock_session) -> None:
        service = KeygenService(mock_session)
        token, build_id = await service.build_aa_req("abc123", "k9")
        raw = base64.b64decode(token)

        decryptor = Cipher(algorithms.AES(aareq_key()), modes.GCM(raw[1:13], raw[-16:])).decryptor()
        payload = json.loads(decryptor.update(raw[13:-16]) + decryptor.finalize())

        assert payload["qh"] == "abc123"
        assert payload["epoch"] == ALLANIME_FALLBACK_EPOCH
        assert payload["buildId"] == ALLANIME_FALLBACK_BUILD_ID
        assert payload["k"] == "k9"
        assert build_id == ALLANIME_FALLBACK_BUILD_ID

    async def test_unknown_lane_raises_value_error(self, mock_session) -> None:
        service = KeygenService(mock_session)
        with pytest.raises(ValueError, match="k99"):
            await service.build_aa_req("abc123", "k99")


class TestAllAnimeKeygenValidation:
    def test_accepts_valid_values(self) -> None:
        keygen = AllAnimeKeygen.from_dict(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": dict(ALLANIME_FALLBACK_LANES),
            }
        )
        assert keygen == AllAnimeKeygen(
            build_id="96",
            epoch=2953,
            lanes=dict(ALLANIME_FALLBACK_LANES),
            query_hashes={},
        )

    def test_accepts_valid_query_hashes(self) -> None:
        keygen = AllAnimeKeygen.from_dict(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": dict(ALLANIME_FALLBACK_LANES),
                "query_hashes": {
                    "search": "a" * 64,
                    "manga": "b" * 64,
                    "chapter": "c" * 64,
                },
            }
        )
        assert keygen is not None
        assert keygen.query_hashes == {
            PersistedQueryName.SEARCH: "a" * 64,
            PersistedQueryName.MANGA: "b" * 64,
            PersistedQueryName.CHAPTER: "c" * 64,
        }

    def test_drops_invalid_query_hashes(self) -> None:
        keygen = AllAnimeKeygen.from_dict(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": dict(ALLANIME_FALLBACK_LANES),
                "query_hashes": {
                    "search": "a" * 64,
                    "manga": "not-hex",
                    "chapter": 12345,
                    "unknown": "d" * 64,
                },
            }
        )
        assert keygen is not None
        assert keygen.query_hashes == {PersistedQueryName.SEARCH: "a" * 64}

    def test_non_dict_query_hashes_yields_empty(self) -> None:
        keygen = AllAnimeKeygen.from_dict(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": dict(ALLANIME_FALLBACK_LANES),
                "query_hashes": "search-hash",
            }
        )
        assert keygen is not None
        assert keygen.query_hashes == {}

    def test_rejects_wrong_length_key(self) -> None:
        keygen = AllAnimeKeygen.from_dict(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": {"k9": "aabb"},
            }
        )
        assert keygen is None

    def test_rejects_empty_lanes(self) -> None:
        assert AllAnimeKeygen.from_dict({"build_id": "96", "epoch": 2953, "lanes": {}}) is None

    def test_rejects_missing_fields(self) -> None:
        assert AllAnimeKeygen.from_dict({}) is None

    def test_rejects_non_dict_lanes(self) -> None:
        keygen = AllAnimeKeygen.from_dict({"build_id": "96", "epoch": 2953, "lanes": "k9"})
        assert keygen is None


class TestKeygenServiceCache:
    async def test_failed_fetch_serves_fallback_and_rearms_ttl(self, mock_session) -> None:
        service = KeygenService(mock_session)

        with patch.object(service, "_fetch", return_value=None) as mock_fetch:
            keygen = await service.get()
            await service.get()

        assert keygen.epoch == ALLANIME_FALLBACK_EPOCH
        assert keygen.build_id == ALLANIME_FALLBACK_BUILD_ID
        # Failed fetch must still re-arm the TTL so the second call skips the re-fetch
        assert mock_fetch.await_count == 1

    async def test_stale_cache_kept_when_refresh_fails(self, mock_session) -> None:
        service = KeygenService(mock_session)
        fetched = fallback_keygen(build_id="99", epoch=9999)
        with patch.object(service, "_fetch", return_value=fetched):
            await service.get()

        service._fetched_at = time.monotonic() - CRYPTO_TTL_SECONDS - 1

        with patch.object(service, "_fetch", return_value=None) as mock_fetch:
            keygen = await service.get()
            await service.get()

        assert keygen.epoch == 9999
        assert mock_fetch.await_count == 1


class TestQueryHash:
    async def test_returns_keygen_hash_when_valid(self, mock_session) -> None:
        service = KeygenService(mock_session)
        keygen = fallback_keygen(query_hashes={PersistedQueryName.SEARCH: "a" * 64})
        with patch.object(service, "get", return_value=keygen):
            assert await service.query_hash(PersistedQueryName.SEARCH) == "a" * 64

    async def test_falls_back_to_constant_when_keygen_lacks_query_hashes(
        self, mock_session
    ) -> None:
        service = KeygenService(mock_session)
        with patch.object(service, "get", return_value=fallback_keygen()):
            assert await service.query_hash(PersistedQueryName.CHAPTER) == CHAPTER_HASH

    async def test_falls_back_when_name_missing_in_keygen(self, mock_session) -> None:
        service = KeygenService(mock_session)
        keygen = fallback_keygen(query_hashes={PersistedQueryName.SEARCH: "a" * 64})
        with patch.object(service, "get", return_value=keygen):
            assert await service.query_hash(PersistedQueryName.MANGA) == MANGA_HASH

    async def test_fetch_failure_falls_back_to_constant(self, mock_session) -> None:
        service = KeygenService(mock_session)
        assert await service.query_hash(PersistedQueryName.SEARCH) == SEARCH_HASH
