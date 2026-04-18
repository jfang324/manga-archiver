from aiohttp import ClientSession

from ....models import Chapter, ContentSource, DownloadResource, Manga
from ...exceptions import ApiError, NotFoundError, RateLimitError
from ..base import Provider
from ..constants import API_HEADERS, DEFAULT_REQUEST_TIMEOUT
from .constants import MANGADEX_RESOURCE_LINKS_URL, MANGADEX_ROOT_URL
from .types import MangaDexChapterResponse, MangaDexDownloadResourceResponse, MangaDexSearchResponse


class MangaDexApiClient(Provider):
    """Client for interacting with the MangaDex API."""

    def __init__(
        self,
        session: ClientSession,
        data_saver: bool = False,
    ) -> None:
        """Initialize the MangaDex API client.

        Args:
            session: The session used for API requests
            data_saver: Whether to download lower quality images.
        """
        super().__init__(session)

        self._source = ContentSource.MANGADEX
        self._data_saver = data_saver

    async def _request(self, url: str, params: dict | None = None) -> dict:
        """Make an HTTP request and return the JSON response.

        Args:
            url: The URL to request
            params: Optional query parameters. Defaults to None

        Returns:
            dict: The JSON response as a dictionary

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: For other API errors
        """
        headers = API_HEADERS.get(ContentSource.MANGADEX, {})

        async with self._session.get(
            url, params=params, headers=headers, timeout=DEFAULT_REQUEST_TIMEOUT
        ) as response:
            if response.status == 404:
                raise NotFoundError(f"Resource not found: {url}")

            if response.status == 429:
                raise RateLimitError(f"Rate limit exceeded for: {url}")

            if response.status != 200:
                raise ApiError(f"API error: {url} returned status {response.status}")

            return await response.json()

    async def search_manga(self, query: str, page: int, page_size: int) -> list[Manga]:
        """
        Search for manga matching the query.

        Args:
            query: The search query string
            page: The page number to fetch (1-indexed)
            page_size: Number of results per page (max 100 per API limits)

        Returns:
            list[Manga]: List of matching manga objects

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: If the API returns any other error
        """
        url: str = f"{MANGADEX_ROOT_URL}?title={query}"
        offset: int = (page - 1) * page_size
        params: dict = {"limit": page_size, "offset": offset}

        response: dict = await self._request(url, params)

        return self._process_manga_data(response)

    def _process_manga_data(self, response: dict) -> list[Manga]:
        """
        Process raw manga data into Manga objects.

        Args:
            response: Raw API response data

        Returns:
            list[Manga]: List of processed manga objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = MangaDexSearchResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        return [
            Manga(id=result.id, title=result.attributes.title, source=self.source)
            for result in raw_data.data
        ]

    async def get_chapters(self, manga_id: str) -> list[Chapter]:
        """
        Retrieve chapters for a given manga.

        Args:
            manga_id: The ID of the manga to get chapters for

        Returns:
            list[Chapter]: List of chapter objects sorted by chapter number

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: If the API returns any other error
        """
        url: str = f"{MANGADEX_ROOT_URL}/{manga_id}/feed"
        params: dict = {
            "translatedLanguage[]": ["en"],
            "limit": 500,
            "includeEmptyPages": 0,
        }

        response: dict = await self._request(url, params)

        return self._process_chapter_data(response)

    def _process_chapter_data(self, response: dict) -> list[Chapter]:
        """
        Process raw chapter data into Chapter objects.

        Args:
            response: Raw API response data

        Returns:
            list[Chapter]: List of processed chapter objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = MangaDexChapterResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        chapters: list[Chapter] = []
        seen_chapters: set[float] = set()

        for result in raw_data.data:
            if result.attributes.chapter in seen_chapters:
                continue

            seen_chapters.add(result.attributes.chapter)
            chapters.append(
                Chapter(
                    id=result.id,
                    title=result.attributes.title,
                    chapter_num=result.attributes.chapter,
                    source=self.source,
                )
            )

        chapters.sort(key=lambda x: x.chapter_num)
        return chapters

    async def get_download_resource(self, chapter_id: str) -> DownloadResource:
        """
        Get download resource information for a chapter.

        Args:
            chapter_id: The ID of the chapter to get download info for

        Returns:
            DownloadResource: Download resource object containing URLs

        Raises:
            NotFoundError: If the chapter is not found
            RateLimitError: If the API rate limit is exceeded
            ApiError: If the API returns any other error
        """
        url: str = f"{MANGADEX_RESOURCE_LINKS_URL}/{chapter_id}"

        response: dict = await self._request(url)

        return self._process_download_resource_data(response)

    def _process_download_resource_data(self, response: dict) -> DownloadResource:
        """
        Process raw download resource data into DownloadResource.

        Args:
            download_resources: Raw API response data

        Returns:
            DownloadResource: Processed download resource object

        Raises:
            ApiError: If response is missing required data
            ValueError: If response is missing required data or chapter data is invalid
        """
        try:
            raw_data = MangaDexDownloadResourceResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        if self._data_saver and raw_data.chapter.data_saver is not None:
            quality = "data-saver"
            urls = raw_data.chapter.data_saver
        else:
            quality = "data"
            urls = raw_data.chapter.data

        return DownloadResource(
            urls=[f"{raw_data.base_url}/{quality}/{raw_data.chapter.hash}/{url}" for url in urls],
            source=self.source,
        )
