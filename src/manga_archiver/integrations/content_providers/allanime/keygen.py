from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
from dataclasses import dataclass

from aiohttp import ClientError, ClientSession, ClientTimeout
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .constants import (
    ALLANIME_FALLBACK_BUILD_ID,
    ALLANIME_FALLBACK_EPOCH,
    ALLANIME_FALLBACK_LANES,
    BROWSER_UA,
    CRYPTO_TTL_SECONDS,
    KEYGEN_URL,
    PERSISTED_QUERY_HASH_FALLBACKS,
    PersistedQueryName,
)

_AES_KEY_LENGTH = 32
_HASH_LENGTH = 32
_AAREQ_TS_BUCKET_MS = 300_000
_KEYGEN_FETCH_TIMEOUT_SECONDS = 15


@dataclass(frozen=True)
class AllAnimeKeygen:
    """Validated keygen values fetched from the shared manga-archiver-keygen repo.

    Attributes:
        build_id: Build identifier the aaReq token and x-build-id header use
        epoch: Crypto epoch used to derive aaReq tokens
        lanes: Content lane name to encrypted key, used for tokens and decoding
        query_hashes: Registered persisted query hashes by known query name
    """

    build_id: str
    epoch: int
    lanes: dict[str, str]
    query_hashes: dict[PersistedQueryName, str]

    @staticmethod
    def from_dict(data: dict) -> AllAnimeKeygen | None:
        """Validate raw keygen JSON into an AllAnimeKeygen, or None when malformed.

        Crypto fields must be well-formed (non-empty build id, integer epoch,
        non-empty lanes of 32-byte hex keys); malformed values reject the whole
        block so they cannot poison the cache. Query hashes are kept only for
        known persisted query names whose values are 32-byte hex digests;
        invalid entries are dropped so they degrade to the hardcoded fallback.

        Args:
            data: Raw keygen data

        Returns:
            AllAnimeKeygen: Validated values, or None when the crypto block is
            invalid
        """
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

        query_hashes: dict[PersistedQueryName, str] = {}
        raw_hashes = data.get("query_hashes")
        if isinstance(raw_hashes, dict):
            for query in PersistedQueryName:
                value = raw_hashes.get(query.value)
                if isinstance(value, str):
                    try:
                        if len(bytes.fromhex(value)) == _HASH_LENGTH:
                            query_hashes[query] = value
                    except ValueError:
                        continue

        return AllAnimeKeygen(
            build_id=build_id,
            epoch=epoch,
            lanes=lanes,
            query_hashes=query_hashes,
        )


def _fallback_keygen() -> AllAnimeKeygen:
    """Return the hardcoded keygen values used when the live fetch fails."""
    return AllAnimeKeygen(
        build_id=ALLANIME_FALLBACK_BUILD_ID,
        epoch=ALLANIME_FALLBACK_EPOCH,
        lanes=dict(ALLANIME_FALLBACK_LANES),
        query_hashes=dict(PERSISTED_QUERY_HASH_FALLBACKS),
    )


class KeygenService:
    """Single source for the remote AllManga keygen values.

    Fetches, validates, caches, and applies the keygen.json values: crypto
    lanes, build id, epoch, persisted query hashes, and aaReq token generation.
    Decryption of tobeparsed responses is handled separately by the pure
    helpers in decode.py.

    Args:
        session: Shared HTTP session, used when fetching keygen values
    """

    def __init__(self, session: ClientSession) -> None:
        self._session = session
        self._cache: AllAnimeKeygen | None = None
        self._fetched_at: float | None = None
        self._fetch_lock = asyncio.Lock()
        self._fallback = _fallback_keygen()

    def invalidate(self) -> None:
        """Drop cached keygen values so the next request re-fetches them."""
        self._cache = None
        self._fetched_at = None

    async def _fetch(self) -> AllAnimeKeygen | None:
        """Fetch and validate current keygen values from the remote endpoint.

        Expected aiohttp client, timeout, and JSON decoding failures return
        None so the caller can fall back to cached or hardcoded values.
        Unexpected exceptions propagate so genuine bugs are not silently
        swallowed.
        """
        headers = {"User-Agent": BROWSER_UA}
        timeout = ClientTimeout(total=_KEYGEN_FETCH_TIMEOUT_SECONDS)
        try:
            async with self._session.get(KEYGEN_URL, headers=headers, timeout=timeout) as resp:
                if resp.status != 200:
                    return None
                data = json.loads(await resp.text())
            if not isinstance(data, dict):
                return None
            return AllAnimeKeygen.from_dict(data)
        except (ClientError, asyncio.TimeoutError, json.JSONDecodeError):
            return None

    def _is_expired(self, now: float) -> bool:
        return self._fetched_at is None or now - self._fetched_at > CRYPTO_TTL_SECONDS

    async def get(self) -> AllAnimeKeygen:
        """Return the current keygen values, refreshing when missing or expired.

        A failed refresh keeps serving the stale cached values, or the
        hardcoded fallback when nothing is cached yet, and re-arms the TTL so
        an unreachable source does not turn every request into a full re-fetch.

        Returns:
            AllAnimeKeygen: Validated keygen values
        """
        cache = self._cache
        if cache is None or self._is_expired(time.monotonic()):
            async with self._fetch_lock:
                cache = self._cache
                if cache is None or self._is_expired(time.monotonic()):
                    fetched = await self._fetch()
                    if fetched is not None:
                        cache = fetched
                    elif cache is None:
                        cache = self._fallback
                    self._cache = cache
                    self._fetched_at = time.monotonic()
        return cache

    async def query_hash(self, query: PersistedQueryName) -> str:
        """Return the current persisted query hash for a query name.

        Prefers the live keygen query_hashes block, falling back to the
        hardcoded constant when the keygen entry is missing or invalid.

        Args:
            query: Persisted query to resolve

        Returns:
            str: The 64-character persisted query hash
        """
        keygen = await self.get()
        return keygen.query_hashes.get(query) or PERSISTED_QUERY_HASH_FALLBACKS[query]

    async def build_aa_req(self, query_hash: str, lane: str) -> tuple[str, str]:
        """Build the encrypted aaReq token for a persisted GraphQL query.

        The token is AES-GCM over a small JSON payload, keyed by the current
        keygen values for the given content lane, with the IV derived from
        (epoch, build id, query hash, timestamp, lane). Timestamps are floored
        to 5-minute buckets to match the site's implementation.

        Args:
            query_hash: The persisted query sha256 hash the token accompanies
            lane: Content lane (e.g. "k9" for chapter pages)

        Returns:
            tuple[str, str]: (aaReq token, build_id) so the caller can attach
            the matching x-build-id header

        Raises:
            ValueError: If the cached keygen values cannot produce a valid key
        """
        keygen = await self.get()
        try:
            key = bytes.fromhex(keygen.lanes[lane])
        except (KeyError, ValueError) as e:
            raise ValueError(f"Invalid keygen key for lane {lane}: {e}") from e

        epoch = keygen.epoch
        build_id = keygen.build_id

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
