import asyncio
import base64
import hashlib
import json
import re
import time

from aiohttp import ClientSession, ClientTimeout
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_MASK,
    ALLANIME_FALLBACK_PART_B,
    BROWSER_UA,
    CDN_IMMUTABLE,
    CRYPTO_TTL_SECONDS,
    MKISSA_URL,
    RESPONSE_STATIC_KEY_SEED,
    SCRAPE_TIMEOUT_SECONDS,
)

_AES_KEY_LENGTH = 32
_AAREQ_TS_BUCKET_MS = 300_000
_MIN_PAYLOAD_LENGTH = 29  # 1 header + 12 IV + 16 tag, plus at least some ciphertext

_crypto_cache: dict | None = None
_crypto_fetched_at: float | None = None
_fetch_lock = asyncio.Lock()


def invalidate_crypto_cache() -> None:
    """Drop cached crypto values so the next request re-fetches them."""
    global _crypto_cache, _crypto_fetched_at
    _crypto_cache = None
    _crypto_fetched_at = None


def _parse_crypto_page(html: str) -> tuple[dict, str] | None:
    """Extract the __aaCrypto object and app entry JS path from the site homepage."""
    assign = re.search(r"window\.__aaCrypto\s*=\s*", html)
    if not assign:
        return None

    # raw_decode handles nested objects and multi-line output, unlike a brace regex
    try:
        aa, _ = json.JSONDecoder().raw_decode(html, assign.end())
    except ValueError:
        return None
    if not isinstance(aa, dict):
        return None

    app_match = re.search(r"_app/immutable/(entry/app\.[^\"']+\.js)", html)
    if not app_match:
        return None

    return aa, app_match.group(1)


def _extract_mask(js: str) -> str | None:
    """Return the mask from a JS chunk if it unambiguously contains one."""
    if "__aaCrypto" not in js:
        return None
    masks = re.findall(r"[0-9a-f]{64}", js)
    if len(masks) == 1:
        return masks[0]
    return None


def _build_crypto(aa: dict, mask: str) -> dict | None:
    """Validate scraped values so malformed data cannot poison the cache."""
    try:
        epoch = int(aa["epoch"])
        part_b = aa["partB"]
        if len(base64.b64decode(part_b, validate=True)) != _AES_KEY_LENGTH:
            return None
    except (KeyError, TypeError, ValueError):
        return None
    return {"epoch": epoch, "partB": part_b, "mask": mask}


async def _fetch_crypto(session: ClientSession) -> dict | None:
    """Scrape current aaReq crypto values from the site's JS bundle.

    Returns None on any failure so the caller can fall back to cached or
    static values.
    """
    headers = {"User-Agent": BROWSER_UA}
    timeout = ClientTimeout(total=SCRAPE_TIMEOUT_SECONDS)
    try:
        async with session.get(MKISSA_URL, headers=headers, timeout=timeout) as resp:
            html = await resp.text()

        parsed = _parse_crypto_page(html)
        if parsed is None:
            return None
        aa, app_path = parsed

        async with session.get(CDN_IMMUTABLE + app_path, headers=headers, timeout=timeout) as resp:
            app_js = await resp.text()

        chunk_refs = dict.fromkeys(re.findall(r"\.\./chunks/([A-Za-z0-9_\-]+\.js)", app_js))
        for ref in chunk_refs:
            try:
                async with session.get(
                    CDN_IMMUTABLE + "chunks/" + ref, headers=headers, timeout=timeout
                ) as resp:
                    js = await resp.text()
            except Exception:  # noqa: S112
                continue
            mask = _extract_mask(js)
            if mask is not None:
                return _build_crypto(aa, mask)
    except Exception:
        return None
    return None


async def _ensure_crypto(session: ClientSession) -> tuple[int, str, str]:
    """Return (epoch, partB, mask), refreshing the cache when missing or expired."""
    global _crypto_cache, _crypto_fetched_at
    async with _fetch_lock:
        now = time.monotonic()
        expired = _crypto_fetched_at is None or now - _crypto_fetched_at > CRYPTO_TTL_SECONDS
        if _crypto_cache is None or expired:
            fetched = await _fetch_crypto(session)
            if fetched is not None:
                _crypto_cache = fetched
            elif _crypto_cache is None:
                _crypto_cache = {
                    "epoch": ALLANIME_FALLBACK_EPOCH,
                    "partB": ALLANIME_FALLBACK_PART_B,
                    "mask": ALLANIME_FALLBACK_MASK,
                }
            # Re-arm the TTL even when the refresh failed, otherwise an
            # unreachable source turns every request into a full re-scrape
            _crypto_fetched_at = now
        return _crypto_cache["epoch"], _crypto_cache["partB"], _crypto_cache["mask"]


def _derive_key(mask_hex: str, part_b: str) -> bytes:
    return bytes(
        a ^ b
        for a, b in zip(
            bytes.fromhex(mask_hex),
            base64.b64decode(part_b),
            strict=True,
        )
    )


def _static_key() -> bytes:
    return hashlib.sha256(RESPONSE_STATIC_KEY_SEED.encode()).digest()


async def generate_aareq(session: ClientSession, query_hash: str) -> str:
    """Build the encrypted aaReq token for a persisted GraphQL query.

    The token is AES-GCM over a small JSON payload, keyed by mask XOR partB,
    with the IV derived from (epoch, query hash, timestamp). Timestamps are
    floored to 5-minute buckets to match the site's implementation.

    Args:
        session: Shared HTTP session, used if crypto values need refreshing
        query_hash: The persisted query sha256 hash the token accompanies

    Returns:
        str: Base64-encoded aaReq token

    Raises:
        ValueError: If the cached crypto values cannot produce a valid key
    """
    epoch, part_b, mask = await _ensure_crypto(session)
    key = _derive_key(mask, part_b)

    ts = int(time.time() * 1000) // _AAREQ_TS_BUCKET_MS * _AAREQ_TS_BUCKET_MS
    payload = json.dumps(
        {"v": 1, "ts": ts, "epoch": epoch, "qh": query_hash},
        separators=(",", ":"),
    )
    iv = hashlib.sha256(f"{epoch}:{query_hash}:{ts}".encode()).digest()[:12]
    cipher = Cipher(algorithms.AES(key), modes.GCM(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(payload.encode()) + encryptor.finalize()
    token = b"\x01" + iv + ciphertext + encryptor.tag
    return base64.b64encode(token).decode()


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


async def decode_tobeparsed(session: ClientSession, encoded: str) -> dict:
    """Decrypt a tobeparsed API payload into response data.

    Tries the aaReq-derived key and the static key, under GCM and the legacy
    CTR scheme. If every candidate fails, the crypto cache is refreshed once
    and decoding retried, in case the server rotated keys mid-TTL.

    Args:
        session: Shared HTTP session, used if crypto values need refreshing
        encoded: Base64 payload from the API's data.tobeparsed field

    Returns:
        dict: Decrypted response data

    Raises:
        ValueError: If the payload is malformed or no known key decodes it
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
        _, part_b, mask = await _ensure_crypto(session)
        result = _try_decode(raw, [_derive_key(mask, part_b), _static_key()])
        if result is not None:
            return result

    raise ValueError("Failed to decode response with any known key")
