import base64

import pytest

from src.manga_archiver.integrations.content_providers.allanime.decode import (
    _static_key,
    decode_tobeparsed,
)
from tests.unit.integrations.content_providers.allanime.conftest import (
    PAYLOAD,
    aareq_key,
    encrypt_gcm,
    encrypt_legacy_ctr,
    fallback_keygen,
)


class TestStaticKey:
    def test_returns_32_byte_key(self) -> None:
        assert len(_static_key()) == 32

    def test_is_deterministic(self) -> None:
        assert _static_key() == _static_key()


class TestDecodeTobeparsed:
    keygen = fallback_keygen()

    def test_decodes_gcm_with_aareq_key(self) -> None:
        encoded = encrypt_gcm(aareq_key(), PAYLOAD)
        assert decode_tobeparsed(encoded, "k9", self.keygen) == PAYLOAD

    def test_decodes_gcm_with_static_key(self) -> None:
        encoded = encrypt_gcm(_static_key(), PAYLOAD)
        assert decode_tobeparsed(encoded, "k9", self.keygen) == PAYLOAD

    def test_decodes_legacy_ctr_payload(self) -> None:
        encoded = encrypt_legacy_ctr(_static_key(), PAYLOAD)
        assert decode_tobeparsed(encoded, "k9", self.keygen) == PAYLOAD

    def test_unknown_key_raises_value_error(self) -> None:
        encoded = encrypt_gcm(b"\x42" * 32, PAYLOAD)
        with pytest.raises(ValueError, match="any known key"):
            decode_tobeparsed(encoded, "k9", self.keygen)

    def test_unknown_lane_raises_value_error(self) -> None:
        encoded = encrypt_gcm(aareq_key(), PAYLOAD)
        with pytest.raises(ValueError, match="lane k99"):
            decode_tobeparsed(encoded, "k99", self.keygen)

    def test_short_payload_raises_value_error(self) -> None:
        encoded = base64.b64encode(b"short").decode()
        with pytest.raises(ValueError, match="too short"):
            decode_tobeparsed(encoded, "k9", self.keygen)

    def test_invalid_base64_raises_value_error(self) -> None:
        with pytest.raises(ValueError, match="Failed to decode"):
            decode_tobeparsed("!!!not-base64!!!", "k9", self.keygen)
