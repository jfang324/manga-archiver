import base64
import json
from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
)
from src.manga_archiver.integrations.content_providers.allanime.keygen import (
    AllAnimeKeygen,
    KeygenService,
)

PAYLOAD = {"chapterPages": {"edges": []}}
IV = b"\x0a" * 12


def aareq_key(lane: str = "k9") -> bytes:
    return bytes.fromhex(ALLANIME_FALLBACK_LANES[lane])


def encrypt_gcm(key: bytes, payload: dict) -> str:
    encryptor = Cipher(algorithms.AES(key), modes.GCM(IV)).encryptor()
    ciphertext = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
    return base64.b64encode(b"\x01" + IV + ciphertext + encryptor.tag).decode()


def encrypt_legacy_ctr(key: bytes, payload: dict) -> str:
    encryptor = Cipher(algorithms.AES(key), modes.CTR(IV + b"\x00\x00\x00\x02")).encryptor()
    ciphertext = encryptor.update(json.dumps(payload).encode()) + encryptor.finalize()
    # The legacy scheme's trailing 16 bytes are not a valid GCM tag
    return base64.b64encode(b"\x01" + IV + ciphertext + b"\x00" * 16).decode()


def fallback_keygen(**overrides) -> AllAnimeKeygen:
    values: dict = {
        "build_id": ALLANIME_FALLBACK_BUILD_ID,
        "epoch": ALLANIME_FALLBACK_EPOCH,
        "lanes": dict(ALLANIME_FALLBACK_LANES),
        "query_hashes": {},
    }
    values.update(overrides)
    return AllAnimeKeygen(**values)


@pytest.fixture(autouse=True)
def stub_crypto() -> Iterator[AsyncMock]:
    """Stub KeygenService._fetch so tests never fetch live keygen values from GitHub.

    Failing fetches make the service fall back to the hardcoded keygen values.
    """
    with patch.object(KeygenService, "_fetch", return_value=None) as mock_fetch:
        yield mock_fetch
