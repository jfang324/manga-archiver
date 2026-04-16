"""AllManga response decoding utilities."""

import base64
import json

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from ...exceptions import ApiError


def _derive_key() -> bytes:
    """Derive AES key from AllManga's secret string.

    Secret string extracted from AllManga's JavaScript bundle.
    """
    # Secret extracted from reverse-engineered JS: "P7K2RGbFgauVtmiS"
    s = "P7K2RGbFgauVtmiS"[::-1]  # Reverse to "SimtvauFgBR2K7P"
    digest = hashes.Hash(hashes.SHA256())
    digest.update(s.encode("utf-8"))

    return digest.finalize()


def decode_tobeparsed(encoded: str) -> dict:
    """Decode AllManga's encrypted API response.

    Args:
        encoded: The base64-encoded encrypted string from API

    Returns:
        dict: Decoded JSON response as dict

    Raises:
        ApiError: If decryption fails
    """
    try:
        raw = base64.b64decode(encoded)
        iv = raw[:12]
        ciphertext_and_tag = raw[12:]

        key = _derive_key()
        aesgcm = AESGCM(key)
        decrypted = aesgcm.decrypt(iv, ciphertext_and_tag, None)

        return json.loads(decrypted.decode("utf-8"))
    except Exception as e:
        raise ApiError(f"Failed to decode response: {e}") from e
