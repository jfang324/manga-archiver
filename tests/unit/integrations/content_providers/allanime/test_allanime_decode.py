import asyncio
import base64
import json
import time
from unittest.mock import AsyncMock, MagicMock, patch

import aiohttp
import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.manga_archiver.integrations.content_providers.allanime import decode
from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
    CRYPTO_TTL_SECONDS,
)
from tests.conftest import AsyncContextManagerMock

# Captured at import time, before the autouse stub_crypto fixture patches it
_real_ensure_keygen = decode._ensure_keygen

PAYLOAD = {"chapterPages": {"edges": []}}
IV = b"\x0a" * 12


def _aareq_key(lane: str = "k9") -> bytes:
    return bytes.fromhex(ALLANIME_FALLBACK_LANES[lane])


def _encrypt_gcm(key: bytes, payload: dict) -> str:
    encryptor = Cipher(algorithms.AES(key), modes.GCM(IV)).encryptor()
    ciphertext = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
    return base64.b64encode(b"\x01" + IV + ciphertext + encryptor.tag).decode()


def _encrypt_legacy_ctr(key: bytes, payload: dict) -> str:
    encryptor = Cipher(algorithms.AES(key), modes.CTR(IV + b"\x00\x00\x00\x02")).encryptor()
    ciphertext = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
    # The legacy scheme's trailing 16 bytes are not a valid GCM tag
    return base64.b64encode(b"\x01" + IV + ciphertext + b"\x00" * 16).decode()


class TestDecodeTobeparsed:
    async def test_decodes_gcm_with_aareq_key(self, mock_session) -> None:
        encoded = _encrypt_gcm(_aareq_key(), PAYLOAD)
        assert await decode.decode_tobeparsed(mock_session, encoded, "k9") == PAYLOAD

    async def test_decodes_gcm_with_static_key(self, mock_session) -> None:
        encoded = _encrypt_gcm(decode._static_key(), PAYLOAD)
        assert await decode.decode_tobeparsed(mock_session, encoded, "k9") == PAYLOAD

    async def test_decodes_legacy_ctr_payload(self, mock_session) -> None:
        encoded = _encrypt_legacy_ctr(decode._static_key(), PAYLOAD)
        assert await decode.decode_tobeparsed(mock_session, encoded, "k9") == PAYLOAD

    async def test_unknown_key_raises_value_error(self, mock_session) -> None:
        encoded = _encrypt_gcm(b"\x42" * 32, PAYLOAD)
        with pytest.raises(ValueError, match="any known key"):
            await decode.decode_tobeparsed(mock_session, encoded, "k9")

    async def test_unknown_lane_raises_value_error(self, mock_session) -> None:
        encoded = _encrypt_gcm(_aareq_key(), PAYLOAD)
        with pytest.raises(ValueError, match="lane k99"):
            await decode.decode_tobeparsed(mock_session, encoded, "k99")

    async def test_stale_keygen_without_lane_recovers_after_refresh(self, mock_session) -> None:
        decode.invalidate_crypto_cache()
        stale = {
            "build_id": ALLANIME_FALLBACK_BUILD_ID,
            "epoch": ALLANIME_FALLBACK_EPOCH,
            "lanes": {"k2": ALLANIME_FALLBACK_LANES["k2"]},
        }
        refreshed = {
            "build_id": ALLANIME_FALLBACK_BUILD_ID,
            "epoch": ALLANIME_FALLBACK_EPOCH,
            "lanes": dict(ALLANIME_FALLBACK_LANES),
        }
        encoded = _encrypt_gcm(_aareq_key(), PAYLOAD)

        with (
            patch.object(decode, "_ensure_keygen", _real_ensure_keygen),
            patch.object(decode, "_fetch_keygen", side_effect=[stale, refreshed]),
        ):
            result = await decode.decode_tobeparsed(mock_session, encoded, "k9")

        assert result == PAYLOAD

    async def test_short_payload_raises_value_error(self, mock_session) -> None:
        encoded = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="too short"):
            await decode.decode_tobeparsed(mock_session, encoded, "k9")

    async def test_invalid_base64_raises_value_error(self, mock_session) -> None:
        with pytest.raises(ValueError, match="Failed to decode"):
            await decode.decode_tobeparsed(mock_session, "!!!not-base64!!!", "k9")


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
        }

    async def test_success_returns_validated_keygen(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text=json.dumps(self._valid_keygen_data()))
        )

        keygen = await decode._fetch_keygen(mock_session)

        assert keygen == self._valid_keygen_data()

    async def test_non_200_status_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(self._mock_response(status=500))

        assert await decode._fetch_keygen(mock_session) is None

    async def test_client_error_returns_none(self, mock_session) -> None:
        mock_session.get.side_effect = aiohttp.ClientError("connection refused")

        assert await decode._fetch_keygen(mock_session) is None

    async def test_timeout_returns_none(self, mock_session) -> None:
        mock_session.get.side_effect = asyncio.TimeoutError

        assert await decode._fetch_keygen(mock_session) is None

    async def test_json_decode_error_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text="not-json")
        )

        assert await decode._fetch_keygen(mock_session) is None

    async def test_malformed_keygen_returns_none(self, mock_session) -> None:
        mock_session.get.return_value = AsyncContextManagerMock(
            self._mock_response(text=json.dumps({"bad": "data"}))
        )

        assert await decode._fetch_keygen(mock_session) is None

    async def test_unexpected_exception_propagates(self, mock_session) -> None:
        mock_session.get.side_effect = RuntimeError("unexpected")

        with pytest.raises(RuntimeError, match="unexpected"):
            await decode._fetch_keygen(mock_session)


class TestGenerateAareq:
    async def test_token_round_trips_with_keygen_key(self, mock_session) -> None:
        token, build_id = await decode.generate_aareq(mock_session, "abc123", "k9")
        raw = base64.b64decode(token)

        decryptor = Cipher(
            algorithms.AES(_aareq_key()), modes.GCM(raw[1:13], raw[-16:])
        ).decryptor()
        payload = json.loads(decryptor.update(raw[13:-16]) + decryptor.finalize())

        assert payload["qh"] == "abc123"
        assert payload["epoch"] == ALLANIME_FALLBACK_EPOCH
        assert payload["buildId"] == ALLANIME_FALLBACK_BUILD_ID
        assert payload["k"] == "k9"
        assert build_id == ALLANIME_FALLBACK_BUILD_ID

    async def test_unknown_lane_raises_value_error(self, mock_session) -> None:
        with pytest.raises(ValueError, match="k99"):
            await decode.generate_aareq(mock_session, "abc123", "k99")


class TestValidKeygen:
    def test_accepts_valid_values(self) -> None:
        keygen = decode._valid_keygen(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": dict(ALLANIME_FALLBACK_LANES),
            }
        )
        assert keygen == {
            "build_id": "96",
            "epoch": 2953,
            "lanes": dict(ALLANIME_FALLBACK_LANES),
        }

    def test_rejects_wrong_length_key(self) -> None:
        keygen = decode._valid_keygen(
            {
                "build_id": "96",
                "epoch": 2953,
                "lanes": {"k9": "aabb"},
            }
        )
        assert keygen is None

    def test_rejects_empty_lanes(self) -> None:
        assert decode._valid_keygen({"build_id": "96", "epoch": 2953, "lanes": {}}) is None

    def test_rejects_missing_fields(self) -> None:
        assert decode._valid_keygen({}) is None

    def test_rejects_non_dict_lanes(self) -> None:
        keygen = decode._valid_keygen({"build_id": "96", "epoch": 2953, "lanes": "k9"})
        assert keygen is None


class TestEnsureKeygenCache:
    async def test_failed_fetch_serves_fallback_and_rearms_ttl(self, mock_session) -> None:
        decode.invalidate_crypto_cache()

        with patch.object(decode, "_fetch_keygen", return_value=None) as mock_fetch:
            keygen = await _real_ensure_keygen(mock_session)
            await _real_ensure_keygen(mock_session)

        assert keygen["epoch"] == ALLANIME_FALLBACK_EPOCH
        assert keygen["build_id"] == ALLANIME_FALLBACK_BUILD_ID
        # Failed fetch must still re-arm the TTL so the second call skips the re-fetch
        assert mock_fetch.await_count == 1

    async def test_stale_cache_kept_when_refresh_fails(self, mock_session) -> None:
        decode.invalidate_crypto_cache()
        fetched = {
            "build_id": "99",
            "epoch": 9999,
            "lanes": dict(ALLANIME_FALLBACK_LANES),
        }
        with patch.object(decode, "_fetch_keygen", return_value=fetched):
            await _real_ensure_keygen(mock_session)

        decode._keygen_fetched_at = time.monotonic() - CRYPTO_TTL_SECONDS - 1

        with patch.object(decode, "_fetch_keygen", return_value=None) as mock_fetch:
            keygen = await _real_ensure_keygen(mock_session)
            await _real_ensure_keygen(mock_session)

        assert keygen["epoch"] == 9999
        assert mock_fetch.await_count == 1
