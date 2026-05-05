from asyncio import Semaphore
from collections.abc import AsyncIterator
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Protocol


class DownloadLimiter(Protocol):
    """Async concurrency limiter for page downloads."""

    def acquire(self) -> AbstractAsyncContextManager[None]:
        """Return a context manager that acquires one download slot."""
        ...


class StaticDownloadLimiter:
    """Fixed-capacity download limiter backed by an asyncio semaphore."""

    def __init__(self, limit: int) -> None:
        """Initialize the limiter.

        Args:
            limit: Maximum number of concurrent downloads

        Raises:
            ValueError: If limit is less than 1
        """
        if limit < 1:
            raise ValueError("limit must be greater than 0")

        self._semaphore = Semaphore(limit)

    @asynccontextmanager
    async def acquire(self) -> AsyncIterator[None]:
        """Acquire one download slot for the duration of the context."""
        async with self._semaphore:
            yield
