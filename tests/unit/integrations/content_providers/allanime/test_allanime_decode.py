import base64
import json
import time
from unittest.mock import patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.manga_archiver.integrations.content_providers.allanime import decode
from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_MASK,
    ALLANIME_FALLBACK_PART_B,
    CRYPTO_TTL_SECONDS,
)

# Captured at import time, before the autouse stub_crypto fixture patches it
_real_ensure_crypto = decode._ensure_crypto

PAYLOAD = {"chapterPages": {"edges": []}}
IV = b"\x0a" * 12


def _aareq_key() -> bytes:
    return decode._derive_key(ALLANIME_FALLBACK_MASK, ALLANIME_FALLBACK_PART_B)


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
        assert await decode.decode_tobeparsed(mock_session, encoded) == PAYLOAD

    async def test_decodes_gcm_with_static_key(self, mock_session) -> None:
        encoded = _encrypt_gcm(decode._static_key(), PAYLOAD)
        assert await decode.decode_tobeparsed(mock_session, encoded) == PAYLOAD

    async def test_decodes_legacy_ctr_payload(self, mock_session) -> None:
        encoded = _encrypt_legacy_ctr(decode._static_key(), PAYLOAD)
        assert await decode.decode_tobeparsed(mock_session, encoded) == PAYLOAD

    async def test_unknown_key_raises_value_error(self, mock_session) -> None:
        encoded = _encrypt_gcm(b"\x42" * 32, PAYLOAD)
        with pytest.raises(ValueError, match="any known key"):
            await decode.decode_tobeparsed(mock_session, encoded)

    async def test_short_payload_raises_value_error(self, mock_session) -> None:
        encoded = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="too short"):
            await decode.decode_tobeparsed(mock_session, encoded)

    async def test_invalid_base64_raises_value_error(self, mock_session) -> None:
        with pytest.raises(ValueError, match="Failed to decode"):
            await decode.decode_tobeparsed(mock_session, "!!!not-base64!!!")


class TestGenerateAareq:
    async def test_token_round_trips_with_derived_key(self, mock_session) -> None:
        token = await decode.generate_aareq(mock_session, "abc123")
        raw = base64.b64decode(token)

        decryptor = Cipher(
            algorithms.AES(_aareq_key()), modes.GCM(raw[1:13], raw[-16:])
        ).decryptor()
        payload = json.loads(decryptor.update(raw[13:-16]) + decryptor.finalize())

        assert payload["qh"] == "abc123"
        assert payload["epoch"] == ALLANIME_FALLBACK_EPOCH


class TestParseCryptoPage:
    def test_parses_nested_multiline_object(self) -> None:
        html = (
            'window.__aaCrypto = {\n"epoch": 4131,\n"partB": "abc",\n"extra": {"x": "}"}\n};\n'
            '<script src="/_app/immutable/entry/app.abc123.js"></script>'
        )
        parsed = decode._parse_crypto_page(html)

        assert parsed is not None
        aa, app_path = parsed
        assert aa["epoch"] == 4131
        assert app_path == "entry/app.abc123.js"

    def test_returns_none_without_crypto_object(self) -> None:
        assert decode._parse_crypto_page("<html></html>") is None

    def test_returns_none_for_invalid_json(self) -> None:
        html = "window.__aaCrypto = {broken};"
        assert decode._parse_crypto_page(html) is None


class TestBuildCrypto:
    def test_accepts_valid_values(self) -> None:
        crypto = decode._build_crypto(
            {"epoch": "4130", "partB": ALLANIME_FALLBACK_PART_B}, ALLANIME_FALLBACK_MASK
        )
        assert crypto == {
            "epoch": 4130,
            "partB": ALLANIME_FALLBACK_PART_B,
            "mask": ALLANIME_FALLBACK_MASK,
        }

    def test_rejects_wrong_length_part_b(self) -> None:
        part_b = base64.b64encode(b"short").decode()
        assert decode._build_crypto({"epoch": 1, "partB": part_b}, ALLANIME_FALLBACK_MASK) is None

    def test_rejects_missing_fields(self) -> None:
        assert decode._build_crypto({}, ALLANIME_FALLBACK_MASK) is None


class TestEnsureCryptoCache:
    async def test_failed_fetch_serves_fallback_and_rearms_ttl(self, mock_session) -> None:
        decode.invalidate_crypto_cache()

        with patch.object(decode, "_fetch_crypto", return_value=None) as mock_fetch:
            epoch, _, _ = await _real_ensure_crypto(mock_session)
            await _real_ensure_crypto(mock_session)

        assert epoch == ALLANIME_FALLBACK_EPOCH
        # Failed fetch must still re-arm the TTL so the second call skips the scrape
        assert mock_fetch.await_count == 1

    async def test_stale_cache_kept_when_refresh_fails(self, mock_session) -> None:
        decode.invalidate_crypto_cache()
        fetched = {"epoch": 1, "partB": ALLANIME_FALLBACK_PART_B, "mask": ALLANIME_FALLBACK_MASK}
        with patch.object(decode, "_fetch_crypto", return_value=fetched):
            await _real_ensure_crypto(mock_session)

        decode._crypto_fetched_at = time.monotonic() - CRYPTO_TTL_SECONDS - 1

        with patch.object(decode, "_fetch_crypto", return_value=None) as mock_fetch:
            epoch, _, _ = await _real_ensure_crypto(mock_session)
            await _real_ensure_crypto(mock_session)

        assert epoch == 1
        assert mock_fetch.await_count == 1
