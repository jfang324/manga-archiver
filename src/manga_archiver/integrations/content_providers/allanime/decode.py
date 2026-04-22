import base64
import hashlib
import json

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes


def _derive_key() -> bytes:
    # New key
    return hashlib.sha256(b"Xot36i3lK3:v1").digest()


def decode_tobeparsed(encoded: str) -> dict:
    try:
        raw = base64.b64decode(encoded)

        if len(raw) < 29:
            raise ValueError(f"Payload too short: {len(raw)} bytes, expected at least 29 bytes")

        # Structure:
        # [0]        = 1 byte header
        # [1:13]     = 12 byte IV
        # [13:-16]   = ciphertext
        # [-16:]     = tag (ignored)

        iv_12 = raw[1:13]
        ciphertext = raw[13:-16]

        # Build CTR IV (16 bytes total)
        ctr_iv = iv_12 + b"\x00\x00\x00\x02"

        key = _derive_key()

        cipher = Cipher(algorithms.AES(key), modes.CTR(ctr_iv))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        result = json.loads(plaintext.decode("utf-8"))

        if not isinstance(result, dict):
            raise ValueError("Invalid response: not a dict")

        return result

    except Exception as e:
        raise ValueError(f"Failed to decode response: {e}") from e
