import json

from aiohttp import ClientSession

from ....models import Chapter, ContentSource, DownloadResource, Manga
from ...exceptions import ApiError, NotFoundError, RateLimitError
from ..base import Provider
from ..constants import API_HEADERS, DEFAULT_REQUEST_TIMEOUT
from .constants import (
    ALLANIME_API_URL,
    CDN_BASE_URL,
    CHAPTER_HASH,
    CHAPTER_PAGES_QUERY,
    MANGA_DETAILS_QUERY,
    MANGA_HASH,
    SEARCH_HASH,
    SEARCH_QUERY,
)
from .decode import decode_tobeparsed
from .types import AllMangaChapterResponse, AllMangaSearchResponse, DownloadResourceResponse


class AllMangaClient(Provider):
    """Client for interacting with the AllManga API."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize AllManga client with HTTP session.

        Args:
            session: The session used for API requests
        """
        super().__init__(session)
        self._source = ContentSource.ALLMANGA

    async def _request(self, url: str, params: dict | None = None) -> dict:
        """Make authenticated API request with required Referer header.

        Args:
            url: API endpoint URL
            params: Query parameters for GraphQL request

        Returns:
            dict: JSON response as a dictionary

        Raises:
            NotFoundError: 404 response
            RateLimitError: 429 response
            ApiError: Other error status codes
        """
        headers = API_HEADERS.get(ContentSource.ALLMANGA, {})

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
        """Search for manga matching query with pagination.

        Args:
            query: Search query string
            page: Page number to fetch (1-indexed)
            page_size: Results per page (max 20 per API limits)

        Returns:
            list[Manga]: List of matching manga objects

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: If the API returns any other error
        """
        variables = SEARCH_QUERY.format(
            query=query,
            limit=page_size,
            page=page,
        )
        extensions = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": SEARCH_HASH}})
        params = {
            "variables": variables,
            "extensions": extensions,
        }

        response = await self._request(ALLANIME_API_URL, params=params)

        return self._parse_search_response(response)

    def _parse_search_response(self, response: dict) -> list[Manga]:
        """Parse search response into Manga objects.

        Args:
            response: Raw API response data

        Returns:
            list[Manga]: List of processed manga objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = AllMangaSearchResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        return [
            Manga(id=result._id, title=result.title, source=self._source)
            for result in raw_data.data.edges
        ]

    async def get_chapters(self, manga_id: str) -> list[Chapter]:
        """Retrieve all chapters for a manga.

        Args:
            manga_id: AllManga manga ID

        Returns:
            list[Chapter]: List of chapter objects sorted by chapter number

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: If the API returns any other error
        """
        variables = MANGA_DETAILS_QUERY.format(manga_id=manga_id)
        extensions = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": MANGA_HASH}})
        params = {
            "variables": variables,
            "extensions": extensions,
        }

        response = await self._request(ALLANIME_API_URL, params=params)

        return self._parse_chapter_data(response, manga_id)

    def _parse_chapter_data(self, response: dict, manga_id: str) -> list[Chapter]:
        """Parse manga details response into Chapter objects.

        Args:
            response: Raw API response data
            manga_id: AllManga manga ID

        Returns:
            list[Chapter]: List of processed chapter objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = AllMangaChapterResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        chapters: list[Chapter] = [
            Chapter(
                id=f"{manga_id}:{chapter_num:g}",
                title="untitled",
                chapter_num=chapter_num,
                source=self._source,
            )
            for chapter_num in raw_data.data.detail.sub
        ]

        chapters.sort(key=lambda x: x.chapter_num)
        return chapters

    async def get_download_resource(self, chapter_id: str) -> DownloadResource:
        """Get image URLs for downloading a chapter.

        Args:
            chapter_id: Format "manga_id:chapter_string"

        Returns:
            DownloadResource: Download resource object containing URLs

        Raises:
            NotFoundError: If the chapter is not found
            RateLimitError: If the API rate limit is exceeded
            ApiError: If the API returns any other error
            ValueError: If chapter_id format is invalid
        """
        try:
            manga_id, chapter_str = chapter_id.split(":", 1)
        except ValueError as e:
            raise ValueError(f"Invalid chapter_id format: {chapter_id}") from e

        if not manga_id or not chapter_str:
            raise ValueError(f"Invalid chapter_id format: {chapter_id}")

        variables = CHAPTER_PAGES_QUERY.format(
            manga_id=manga_id,
            chapter_string=chapter_str,
        )
        extensions = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": CHAPTER_HASH}})
        params = {
            "variables": variables,
            "extensions": extensions,
        }

        response = await self._request(ALLANIME_API_URL, params=params)

        return self._parse_download_resource(response, chapter_id)

    def _parse_download_resource(self, response: dict, chapter_id: str) -> DownloadResource:
        """Parse chapter pages response into DownloadResource.

        Args:
            response: Raw API response data
            chapter_id: The chapter ID being fetched

        Returns:
            DownloadResource: Processed download resource object

        Raises:
            ApiError: If response data is invalid or no URLs found
        """
        response_data = response.get("data", {})

        if not isinstance(response_data, dict):
            raise ApiError("Invalid response: not a dict")

        if "tobeparsed" in response_data:
            response_data = decode_tobeparsed(response_data["tobeparsed"])
            if not isinstance(response_data, dict):
                raise ApiError("Invalid response: tobeparsed is not a dict")

        try:
            download_response = DownloadResourceResponse.from_dict(response_data)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        urls = [
            f"{CDN_BASE_URL}{picture.url}"
            for edge in download_response.pages.edges
            for picture in edge.picture_urls
            if picture.url and picture.url.strip()
        ]

        if not urls:
            raise ApiError(f"No image URLs found for chapter {chapter_id}")

        return DownloadResource(urls=urls, source=self._source)
