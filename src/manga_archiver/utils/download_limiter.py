import asyncio
import time
from collections import deque
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager

DEFAULT_TOKEN_TTL_SECONDS: float = 60.0


class DownloadLimiter:
    """Download limiter with fixed base capacity and expiring burst tokens."""

    def __init__(
        self,
        base_limit: int,
        token_ttl_seconds: float = DEFAULT_TOKEN_TTL_SECONDS,
        time_provider: Callable[[], float] = time.monotonic,
    ) -> None:
        """Initialize the limiter.

        Args:
            base_limit: Number of base concurrent downloads
            token_ttl_seconds: Seconds before clean-success burst tokens expire
            time_provider: Monotonic clock provider

        Raises:
            ValueError: If the limit or token TTL are invalid
        """
        if base_limit < 1:
            raise ValueError("base_limit must be greater than 0")

        if token_ttl_seconds <= 0:
            raise ValueError("token_ttl_seconds must be greater than 0")

        self._base_limit = base_limit
        self._token_ttl_seconds = token_ttl_seconds
        self._time_provider = time_provider

        self._tokens: deque[float] = deque()
        self._base_in_use = 0
        self._condition = asyncio.Condition()

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Acquire one base slot or spend one burst token."""
        is_base_slot = False

        async with self._condition:
            await self._condition.wait_for(self._has_available_slot)

            if self._base_in_use < self._base_limit:
                self._base_in_use += 1
                is_base_slot = True
            else:
                self._tokens.popleft()

        try:
            yield
        finally:
            if is_base_slot:
                async with self._condition:
                    self._base_in_use -= 1
                    self._condition.notify_all()

    async def record_success(self) -> None:
        """Record a clean download success as one expiring burst token."""
        async with self._condition:
            now = self._time_provider()
            self._expire_tokens(now)
            self._tokens.append(now)

            self._condition.notify_all()

    async def record_retryable_error(self) -> None:
        """Clear burst tokens after retryable failure feedback."""
        async with self._condition:
            self._tokens.clear()
            self._condition.notify_all()

    def _has_available_slot(self) -> bool:
        """Return whether a base slot or unexpired burst token is available."""
        self._expire_tokens(self._time_provider())
        return self._base_in_use < self._base_limit or bool(self._tokens)

    def _expire_tokens(self, now: float) -> None:
        """Discard clean-success tokens older than the configured TTL."""
        expiry_cutoff = now - self._token_ttl_seconds

        while self._tokens and self._tokens[0] < expiry_cutoff:
            self._tokens.popleft()
