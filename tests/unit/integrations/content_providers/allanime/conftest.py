from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from src.manga_archiver.integrations.content_providers.allanime import decode
from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
)


@pytest.fixture(autouse=True)
def stub_crypto() -> Iterator[AsyncMock]:
    """Stub _ensure_keygen so tests never fetch live keygen values from GitHub."""
    decode.invalidate_crypto_cache()
    fallback = {
        "build_id": ALLANIME_FALLBACK_BUILD_ID,
        "epoch": ALLANIME_FALLBACK_EPOCH,
        "lanes": dict(ALLANIME_FALLBACK_LANES),
    }
    with patch.object(decode, "_ensure_keygen", return_value=fallback) as mock_ensure:
        yield mock_ensure
    decode.invalidate_crypto_cache()
