import asyncio
from typing import TypeAlias

from aiohttp import ClientSession

from ...models import Chapter, ContentSource, DownloadResource, Manga
from .allanime.client import AllMangaClient
from .mangadex.client import MangaDexApiClient

SearchResults: TypeAlias = tuple[list[Manga], list[tuple[ContentSource, Exception]]]


class ContentProviderManager:
    """Aggregates content from multiple manga providers."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the content provider manager.

        Args:
            session: aiohttp ClientSession for HTTP requests
        """
        self._session = session
        self._providers = {
            ContentSource.MANGADEX: MangaDexApiClient(session),
            ContentSource.ALLMANGA: AllMangaClient(session),
        }

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

        if provider is None:
            raise ValueError(f"Unsupported content source: {source}")

        return await provider.get_chapters(manga_id)

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
            ValueError: If source is not supported
            ApiError: On API errors
            NotFoundError: If chapter not found
            RateLimitError: On rate limit
        """
        provider = self._providers.get(source)

        if provider is None:
            raise ValueError(f"Unsupported content source: {source}")

        return await provider.get_download_resource(chapter_id)
