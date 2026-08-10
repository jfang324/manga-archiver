import asyncio
import base64
import hashlib
import json
import time

from aiohttp import ClientSession, ClientTimeout
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
    BROWSER_UA,
    CRYPTO_TTL_SECONDS,
    KEYGEN_URL,
    RESPONSE_STATIC_KEY_SEED,
)

_AES_KEY_LENGTH = 32
_AAREQ_TS_BUCKET_MS = 300_000
_MIN_PAYLOAD_LENGTH = 29  # 1 header + 12 IV + 16 tag, plus at least some ciphertext
_KEYGEN_FETCH_TIMEOUT_SECONDS = 15

_keygen_cache: dict | None = None
_keygen_fetched_at: float | None = None
_fetch_lock = asyncio.Lock()


def invalidate_crypto_cache() -> None:
    """Drop cached keygen values so the next request re-fetches them."""
    global _keygen_cache, _keygen_fetched_at
    _keygen_cache = None
    _keygen_fetched_at = None


def _build_fallback_keygen() -> dict:
    """Return the hardcoded keygen values used when the live fetch fails."""
    return {
        "build_id": ALLANIME_FALLBACK_BUILD_ID,
        "epoch": ALLANIME_FALLBACK_EPOCH,
        "lanes": dict(ALLANIME_FALLBACK_LANES),
    }


def _valid_keygen(data: dict) -> dict | None:
    """Validate scraped keygen values so malformed data cannot poison the cache."""
    try:
        build_id = data["build_id"]
        epoch = int(data["epoch"])
        lanes = data["lanes"]
        if not isinstance(build_id, str) or not build_id:
            return None
        if not isinstance(lanes, dict) or not lanes:
            return None
        for lane, key in lanes.items():
            if not isinstance(lane, str) or not lane:
                return None
            if not isinstance(key, str) or len(bytes.fromhex(key)) != _AES_KEY_LENGTH:
                return None
    except (KeyError, TypeError, ValueError):
        return None
    return {"build_id": build_id, "epoch": epoch, "lanes": lanes}


async def _fetch_keygen(session: ClientSession) -> dict | None:
    """Fetch current crypto values from the shared AllAnime keygen endpoint."""
    headers = {"User-Agent": BROWSER_UA}
    timeout = ClientTimeout(total=_KEYGEN_FETCH_TIMEOUT_SECONDS)
    try:
        async with session.get(KEYGEN_URL, headers=headers, timeout=timeout) as resp:
            if resp.status != 200:
                return None
            data = json.loads(await resp.text())
        if not isinstance(data, dict):
            return None
        return _valid_keygen(data)
    except Exception:
        return None


async def _ensure_keygen(session: ClientSession) -> dict:
    """Return the keygen values, refreshing the cache when missing or expired."""
    global _keygen_cache, _keygen_fetched_at
    async with _fetch_lock:
        now = time.monotonic()
        expired = _keygen_fetched_at is None or now - _keygen_fetched_at > CRYPTO_TTL_SECONDS
        if _keygen_cache is None or expired:
            fetched = await _fetch_keygen(session)
            if fetched is not None:
                _keygen_cache = fetched
            elif _keygen_cache is None:
                _keygen_cache = _build_fallback_keygen()
            # Re-arm the TTL even when the refresh failed, otherwise an
            # unreachable source turns every request into a full re-fetch
            _keygen_fetched_at = now
        return _keygen_cache


def _static_key(seed: str = RESPONSE_STATIC_KEY_SEED) -> bytes:
    return hashlib.sha256(seed.encode()).digest()


async def generate_aareq(session: ClientSession, query_hash: str, lane: str) -> tuple[str, str]:
    """Build the encrypted aaReq token for a persisted GraphQL query.

    The token is AES-GCM over a small JSON payload, keyed by the current
    AllAnime keygen values for the given content lane, with the IV derived
    from (epoch, build id, query hash, timestamp, lane). Timestamps are
    floored to 5-minute buckets to match the site's implementation.

    Args:
        session: Shared HTTP session, used if keygen values need refreshing
        query_hash: The persisted query sha256 hash the token accompanies
        lane: Content lane (e.g. "k9" for chapter pages)

    Returns:
        tuple[str, str]: (aaReq token, build_id) so the caller can attach the
        matching x-build-id header

    Raises:
        ValueError: If the cached keygen values cannot produce a valid key
    """
    keygen = await _ensure_keygen(session)
    try:
        key = bytes.fromhex(keygen["lanes"][lane])
    except (KeyError, ValueError) as e:
        raise ValueError(f"Invalid keygen key for lane {lane}: {e}") from e

    epoch = keygen["epoch"]
    build_id = keygen["build_id"]

    ts = int(time.time() * 1000) // _AAREQ_TS_BUCKET_MS * _AAREQ_TS_BUCKET_MS
    payload = json.dumps(
        {
            "v": 1,
            "ts": ts,
            "epoch": epoch,
            "buildId": build_id,
            "qh": query_hash,
            "k": lane,
        },
        separators=(",", ":"),
    )
    iv = hashlib.sha256(f"{epoch}:{build_id}:{query_hash}:{ts}:{lane}".encode()).digest()[:12]
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload.encode()) + encryptor.finalize()
    token = b"\x01" + iv + ciphertext + encryptor.tag
    return base64.b64encode(token).decode(), build_id


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


async def decode_tobeparsed(session: ClientSession, encoded: str, lane: str) -> dict:
    """Decrypt a tobeparsed API payload into response data.

    Tries the lane's keygen-derived key and the static key, under GCM and the
    legacy CTR scheme. If every candidate fails, the keygen cache is refreshed
    once and decoding retried, in case the server rotated keys mid-TTL.

    Args:
        session: Shared HTTP session, used if keygen values need refreshing
        encoded: Base64 payload from the API's data.tobeparsed field
        lane: Content lane the response belongs to (e.g. "k9")

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

    for refresh in (False, True):
        if refresh:
            invalidate_crypto_cache()
        keygen = await _ensure_keygen(session)
        if lane not in keygen["lanes"]:
            raise ValueError(f"Invalid keygen key for lane {lane}: lane not found")
        keys: list[bytes] = [_static_key(RESPONSE_STATIC_KEY_SEED)]
        try:
            keys.insert(0, bytes.fromhex(keygen["lanes"][lane]))
        except ValueError:
            pass
        result = _try_decode(raw, keys)
        if result is not None:
            return result

    raise ValueError("Failed to decode response with any known key")
