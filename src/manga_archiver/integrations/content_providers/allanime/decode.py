import base64
import hashlib
import json
import time

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

# Constants used by AllAnime request token generation
ALLANIME_EPOCH: int = 4128
ALLANIME_BUILD_ID: str = "9"


def _quantize_timestamp(ms: int) -> int:
    """Quantise a millisecond timestamp to a 5‑minute window.

    AllAnime groups timestamps into 5‑minute buckets. The function
    rounds the given ``ms`` value down to the nearest multiple of
    ``300_000`` (5 minutes in milliseconds).
    """
    return (ms // 300_000) * 300_000


def _derive_allanime_key() -> bytes:
    """Return the static AES‑GCM key used by AllAnime.

    The key is a 32‑byte value that was reverse‑engineered from the
    official AllAnime client. It is kept private because it is an
    implementation detail of the decryption routine.
    """
    return bytes.fromhex("22196fa6afca95309fdabe9a3534b87cd2454e50efeabfcbdbdfd3de678b3982")


def generate_aareq(query_hash: str) -> str:
    """Create the `aaReq` token required by AllAnime.

    The token is an AES‑GCM encrypted payload containing a version,
    timestamp (quantised to a 5‑minute window), a static epoch and build
    identifier, and the query hash. The resulting byte string is prefixed
    with ``0x01`` and base‑64 encoded.

    Args:
        query_hash: The persisted‑query SHA‑256 hash for the request.

    Returns:
        A base‑64 encoded string that can be sent as the ``aaReq`` field in
        the GraphQL ``extensions`` payload.
    """
    ts = _quantize_timestamp(int(time.time() * 1000))
    payload = json.dumps(
        {"v": 1, "ts": ts, "epoch": ALLANIME_EPOCH, "buildId": ALLANIME_BUILD_ID, "qh": query_hash},
        separators=(",", ":"),
    )
    iv = hashlib.sha256(
        f"{ALLANIME_EPOCH}:{ALLANIME_BUILD_ID}:{query_hash}:{ts}".encode()
    ).digest()[:12]
    key = _derive_allanime_key()
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload.encode()) + encryptor.finalize()
    tag = encryptor.tag
    token = b"\x01" + iv + ciphertext + tag
    return base64.b64encode(token).decode()


def decode_tobeparsed(encoded: str) -> dict:
    """Decrypt and decode the ``tobeparsed`` field from an AllAnime response.

    The server returns an encrypted payload when the GraphQL query
    requires additional processing. This function base‑64 decodes the
    input, extracts the IV, ciphertext and authentication tag, and then
    decrypts using AES‑GCM with the static key.

    Args:
        encoded: Base‑64 encoded payload from the ``tobeparsed`` field.

    Returns:
        The decoded JSON object as a ``dict``.

    Raises:
        ValueError: If decoding fails, the payload is malformed, or the
            decrypted plaintext does not represent a JSON object.
    """
    try:
        raw = base64.b64decode(encoded)

        if len(raw) < 29:
            raise ValueError(f"Payload too short: {len(raw)} bytes, expected at least 29 bytes")

        iv = raw[1:13]
        ciphertext = raw[13:-16]
        tag = raw[-16:]

        key = _derive_allanime_key()
        cipher = Cipher(algorithms.AES(key), modes.GCM(iv, tag))
        decryptor = cipher.decryptor()
        plaintext = decryptor.update(ciphertext) + decryptor.finalize()

        result = json.loads(plaintext.decode("utf-8"))

        if not isinstance(result, dict):
            raise ValueError("Invalid response: not a dict")

        return result

    except Exception as e:
        raise ValueError(f"Failed to decode response: {e}") from e
