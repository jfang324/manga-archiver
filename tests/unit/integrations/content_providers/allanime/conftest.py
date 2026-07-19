from collections.abc import Iterator
from unittest.mock import AsyncMock, patch

import pytest

from src.manga_archiver.integrations.content_providers.allanime import decode
from src.manga_archiver.integrations.content_providers.allanime.constants import (
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_MASK,
    ALLANIME_FALLBACK_PART_B,
)


@pytest.fixture(autouse=True)
def stub_crypto() -> Iterator[AsyncMock]:
    """Stub _ensure_crypto so tests never fetch live crypto constants from mkissa.to/CDN."""
    decode.invalidate_crypto_cache()
    with patch.object(
        decode,
        "_ensure_crypto",
        return_value=(ALLANIME_FALLBACK_EPOCH, ALLANIME_FALLBACK_PART_B, ALLANIME_FALLBACK_MASK),
    ) as mock_ensure:
        yield mock_ensure
    decode.invalidate_crypto_cache()
