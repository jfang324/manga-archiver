import base64
import hashlib
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import RESPONSE_STATIC_KEY_SEED
from .keygen import AllAnimeKeygen

_MIN_PAYLOAD_LENGTH = 29  # 1 header + 12 IV + 16 tag, plus at least some ciphertext


def _static_key(seed: str = RESPONSE_STATIC_KEY_SEED) -> bytes:
    """Derive the static fallback key from the known response seed."""
    return hashlib.sha256(seed.encode()).digest()


def _try_decode(raw: bytes, keys: list[bytes]) -> dict | None:
    """Try decrypting a payload with each key under GCM, then legacy CTR."""
    iv = raw[1:13]
    ciphertext = raw[13:-16]
    tag = raw[-16:]

    # CTR ignoring the trailing tag is the scheme the API has flip-flopped
    # back to before; JSON parsing doubles as the integrity check there
    cipher_modes = [modes.GCM(iv, tag), modes.CTR(iv + b"\x00\x00\x00\x02")]
    for mode in cipher_modes:
        for key in keys:
            try:
                decryptor = Cipher(algorithms.AES(key), mode).decryptor()
                plaintext = decryptor.update(ciphertext) + decryptor.finalize()
                result = json.loads(plaintext.decode("utf-8"))
                if isinstance(result, dict):
                    return result
            except Exception:  # noqa: S112, PERF203
                continue
    return None


def decode_tobeparsed(encoded: str, lane: str, keygen: AllAnimeKeygen) -> dict:
    """Decrypt a tobeparsed API payload into response data using keygen values.

    Tries the lane's keygen-derived key and the static fallback key under both
    the GCM and legacy CTR schemes. Keygen is resolved and refreshed by
    KeygenService, so this function stays a pure single-pass decode.

    Args:
        encoded: Base64 payload from the API's data.tobeparsed field
        lane: Content lane the response belongs to (e.g. "k9")
        keygen: Validated keygen values used to derive decryption keys

    Returns:
        dict: Decrypted response data

    Raises:
        ValueError: If the payload is malformed, the lane is unknown, or no
            known key decodes it
    """
    try:
        raw = base64.b64decode(encoded)
    except Exception as e:
        raise ValueError(f"Failed to decode response: {e}") from e

    if len(raw) < _MIN_PAYLOAD_LENGTH:
        raise ValueError(
            f"Payload too short: {len(raw)} bytes, expected at least {_MIN_PAYLOAD_LENGTH} bytes"
        )

    if lane not in keygen.lanes:
        raise ValueError(f"Invalid keygen key for lane {lane}: lane not found")

    keys: list[bytes] = [_static_key()]
    try:
        keys.insert(0, bytes.fromhex(keygen.lanes[lane]))
    except ValueError:
        pass

    result = _try_decode(raw, keys)
    if result is None:
        raise ValueError("Failed to decode response with any known key")
    return result
