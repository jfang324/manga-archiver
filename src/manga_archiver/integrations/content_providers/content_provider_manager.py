import asyncio
import logging
from dataclasses import dataclass
from typing import TypeAlias

from aiohttp import ClientSession

from ...types import Chapter, ContentSource, DownloadResource, Manga
from .base import Provider
from .mangadex.client import MangaDexApiClient

logger = logging.getLogger(__name__)

SearchResults: TypeAlias = tuple[list[Manga], list[tuple[ContentSource, Exception]]]


@dataclass
class ProviderSearchResult:
    """Result from a single provider's search operation.

    Attributes:
        provider: The source that was searched
        results: Manga list if successful, None if failed
        error: Exception if failed, None if successful
    """

    provider: ContentSource
    results: list[Manga] | None = None
    error: Exception | None = None


class ContentProviderManager:
    """Aggregates content from multiple manga providers.

    Searches all providers in parallel and provides a unified interface
    for chapter and resource retrieval.
    """

    def __init__(self, session: ClientSession) -> None:
        """Initialize the content provider manager.

        Args:
            session: aiohttp ClientSession for HTTP requests

        Creates provider instances internally. Currently includes MangaDex,
        with support for additional providers planned.
        """
        self._session = session
        self._providers = {
            ContentSource.MANGADEX: MangaDexApiClient(session),
        }

    async def search_manga(self, query: str, timeout_per_provider: float = 10.0) -> SearchResults:
        """Search all providers simultaneously and return aggregated results.

        Args:
            query: Search query string
            timeout_per_provider: Maximum seconds to wait per provider (default: 10.0)

        Returns:
            Tuple of (successful results, error list). Results from successful
            providers are returned; failed providers are logged and returned in
            the error list for consumer visibility.
        """
        tasks = [
            self._safe_search(source, client, query, timeout=timeout_per_provider)
            for source, client in self._providers.items()
        ]

        results = await asyncio.gather(*tasks)

        all_manga: list[Manga] = []
        errors: list[tuple[ContentSource, Exception]] = []

        for result in results:
            if result.results is not None:
                all_manga.extend(result.results)
            elif result.error is not None:
                errors.append((result.provider, result.error))

        if errors:
            logger.error(
                "Search partially failed: %d of %d providers errored",
                len(errors),
                len(self._providers),
            )

        return all_manga, errors

    async def _safe_search(
        self,
        source: ContentSource,
        client: Provider,
        query: str,
        timeout: float,
    ) -> ProviderSearchResult:
        """Execute search with timeout and error handling.

        Args:
            source: Provider source identifier
            client: Provider instance to search
            query: Search query string
            timeout: Timeout in seconds

        Returns:
            ProviderSearchResult with results or error information
        """
        try:
            results = await asyncio.wait_for(client.search_manga(query), timeout=timeout)
            return ProviderSearchResult(provider=source, results=results)
        except asyncio.TimeoutError:
            logger.error(
                "Provider %s timed out after %ss for query '%s'",
                source,
                timeout,
                query,
            )
            return ProviderSearchResult(
                provider=source, error=TimeoutError(f"Timeout after {timeout}s")
            )
        except Exception as e:
            logger.error("Provider %s failed for query '%s': %s", source, query, str(e))
            return ProviderSearchResult(provider=source, error=e)

    async def get_chapters(self, source: ContentSource, manga_id: str) -> list[Chapter]:
        """Retrieve chapters from a specific provider.

        Args:
            source: Which provider to query (from manga.source)
            manga_id: ID of manga at that provider

        Returns:
            list[Chapter] from the specified provider

        Raises:
            ValueError: If source is not supported
            ApiError: On API errors
            NotFoundError: If manga not found
            RateLimitError: On rate limit
        """
        provider = self._providers.get(source)

        if provider is None:
            raise ValueError(f"Unsupported content source: {source}")

        try:
            return await provider.get_chapters(manga_id)
        except Exception as e:
            logger.error(
                "Failed to get chapters from %s for manga %s: %s",
                source,
                manga_id,
                str(e),
            )
            raise

    async def get_download_resource(
        self, source: ContentSource, chapter_id: str
    ) -> DownloadResource:
        """Get download URLs from a specific provider.

        Args:
            source: Which provider to query
            chapter_id: ID of chapter at that provider

        Returns:
            DownloadResource with URLs for images

        Raises:
            ApiError: On API errors
            NotFoundError: If chapter not found
            RateLimitError: On rate limit
        """
        provider = self._providers[source]
        try:
            return await provider.get_download_resource(chapter_id)
        except Exception as e:
            logger.error(
                "Failed to get download resource from %s for chapter %s: %s",
                source,
                chapter_id,
                str(e),
            )
            raise
