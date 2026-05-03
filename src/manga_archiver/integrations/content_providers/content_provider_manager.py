import asyncio
from asyncio import Semaphore
from typing import TypeAlias

from aiohttp import ClientSession

from ...constants.defaults import DEFAULT_DOWNLOAD_RATE_LIMIT, DEFAULT_PROVIDER_RATE_LIMIT
from ...models import Chapter, ContentSource, DownloadResource, Manga
from ...repositories import PageCacheRepository
from .allanime.client import AllMangaClient
from .mangadex.client import MangaDexApiClient

SearchResults: TypeAlias = tuple[list[Manga], list[tuple[ContentSource, Exception]]]


class ContentProviderManager:
    """Aggregates content from multiple manga providers."""

    def __init__(
        self,
        session: ClientSession,
        resolve_rate_limit: int = DEFAULT_PROVIDER_RATE_LIMIT,
        download_rate_limit: int = DEFAULT_DOWNLOAD_RATE_LIMIT,
    ) -> None:
        """Initialize the content provider manager.

        Args:
            session: aiohttp ClientSession for HTTP requests
            resolve_rate_limit: Per-provider rate limit for resolve operations
            download_rate_limit: Per-provider rate limit for download operations
        """
        if resolve_rate_limit < 1:
            raise ValueError("resolve_rate_limit must be greater than 0")

        if download_rate_limit < 1:
            raise ValueError("download_rate_limit must be greater than 0")

        self._session = session
        self._providers = {
            ContentSource.MANGADEX: MangaDexApiClient(session),
            ContentSource.ALLMANGA: AllMangaClient(session),
        }
        self._resolve_semaphores: dict[ContentSource, Semaphore] = {
            source: Semaphore(resolve_rate_limit) for source in ContentSource
        }
        self._download_semaphores: dict[ContentSource, Semaphore] = {
            source: Semaphore(download_rate_limit) for source in ContentSource
        }
        self._page_cache = PageCacheRepository()

    async def search_manga(self, query: str, page: int, page_size: int) -> SearchResults:
        """Search all providers in parallel.

        Args:
            query: Search query string
            page: Page number to fetch
            page_size: Number of results per page

        Returns:
            SearchResults: Tuple of (successful results, errors). Errors contain exceptions
            from failed providers.
        """
        source_client_pairs = list(self._providers.items())
        tasks = [client.search_manga(query, page, page_size) for _, client in source_client_pairs]

        results = await asyncio.gather(*tasks, return_exceptions=True)

        all_manga: list[Manga] = []
        errors: list[tuple[ContentSource, Exception]] = []

        for (source, _), result in zip(source_client_pairs, results, strict=True):
            if isinstance(result, Exception):
                errors.append((source, result))
            elif isinstance(result, list):
                all_manga.extend(result)
            else:
                errors.append(
                    (
                        source,
                        TypeError(
                            f"Unexpected results type from provider {source}: {type(result).__name__}"
                        ),
                    )
                )

        all_manga.sort(key=lambda manga: manga.title.lower())

        return all_manga, errors

    async def get_chapters(self, source: ContentSource, manga_id: str) -> list[Chapter]:
        """Retrieve chapters from a specific provider.

        Args:
            source: Which provider to query
            manga_id: ID of manga at that provider

        Returns:
            list[Chapter]: List of chapter objects

        Raises:
            ValueError: If source is not supported
            ApiError: On API errors
            NotFoundError: If manga not found
            RateLimitError: On rate limit
        """
        provider = self._providers.get(source)
        semaphore = self._resolve_semaphores.get(source)

        if provider is None or semaphore is None:
            raise ValueError(f"Unsupported content source: {source}")

        async with semaphore:
            return await provider.get_chapters(manga_id)

    async def get_download_resource(
        self, source: ContentSource, chapter_id: str
    ) -> DownloadResource:
        """Get download URLs from a specific provider.

        Args:
            source: Which provider to query
            chapter_id: ID of chapter at that provider

        Returns:
            DownloadResource: DownloadResource with URLs for images

        Raises:
            ValueError: If source is not supported
            ApiError: On API errors
            NotFoundError: If chapter not found
            RateLimitError: On rate limit
        """
        provider = self._providers.get(source)
        semaphore = self._resolve_semaphores.get(source)

        if provider is None or semaphore is None:
            raise ValueError(f"Unsupported content source: {source}")

        cached_urls = self._page_cache.get(source, chapter_id)
        if cached_urls:
            return DownloadResource(urls=cached_urls, source=source)

        async with semaphore:
            result = await provider.get_download_resource(chapter_id)

        if result.urls:
            self._page_cache.set(source, chapter_id, result.urls)

        return result

    def get_download_semaphore(self, source: ContentSource) -> Semaphore:
        """Get the download semaphore for a specific provider.

        Args:
            source: Which provider to get semaphore for

        Returns:
            Semaphore: Semaphore for rate limiting download operations

        Raises:
            ValueError: If source is not supported
        """
        semaphore = self._download_semaphores.get(source)

        if semaphore is None:
            raise ValueError(f"Unsupported content source: {source}")

        return semaphore

    def invalidate_cache(self, source: ContentSource, chapter_id: str) -> None:
        """Invalidate cached URLs for a chapter.

        Args:
            source: Which provider to invalidate
            chapter_id: ID of chapter to invalidate cache for
        """
        self._page_cache.delete(source, chapter_id)
