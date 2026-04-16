import json
import logging

from aiohttp import ClientSession

from ....types import Chapter, ContentSource, DownloadResource, Manga
from ...exceptions import ApiError, NotFoundError, RateLimitError
from ..base import Provider
from ..header_mappings import API_HEADERS
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
from .types import ChapterPagesData, MangaChaptersDetail, SearchResult

logger = logging.getLogger(__name__)


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

        async with self._session.get(url, params=params, headers=headers) as response:
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

        try:
            response = await self._request(ALLANIME_API_URL, params=params)
            return self._parse_search_response(response)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error searching manga: %s", e)
            raise

    def _parse_search_response(self, data: dict) -> list[Manga]:
        """Parse search response into Manga objects.

        Args:
            data: Raw API response data

        Returns:
            list[Manga]: List of processed manga objects
        """
        edges = data.get("data", {}).get("mangas", {}).get("edges", [])
        results: list[Manga] = []

        for edge in edges:
            result = self._parse_search_result(edge)
            if result:
                results.append(result)

        return results

    def _parse_search_result(self, edge: dict) -> Manga | None:
        """Parse single search result edge into Manga object.

        Args:
            edge: Raw edge dictionary from search response

        Returns:
            Manga object if valid, None otherwise
        """
        try:
            result = SearchResult.from_dict(edge)
        except ValueError:
            logger.error("Error parsing search result: %s", edge)
            return None

        return Manga(id=result._id, title=result.title, source=self._source)

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

        try:
            response = await self._request(ALLANIME_API_URL, params=params)
            return self._parse_chapter_data(response, manga_id)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error retrieving chapters: %s", e)
            raise

    def _parse_chapter_data(self, data: dict, manga_id: str) -> list[Chapter]:
        """Parse manga details response into Chapter objects.

        Args:
            data: Raw API response data
            manga_id: AllManga manga ID

        Returns:
            list[Chapter]: List of processed chapter objects

        Raises:
            NotFoundError: If no chapters are found
        """
        chapters_detail = data.get("data", {}).get("manga", {})

        try:
            detail = MangaChaptersDetail.from_dict(
                chapters_detail.get("availableChaptersDetail", {})
            )
        except ValueError as e:
            raise NotFoundError(f"No chapters found for manga {manga_id}") from e

        chapters = []

        for chapter_str in detail.sub:
            if not chapter_str:
                continue

            try:
                chapter_num = float(chapter_str)
            except ValueError:
                logger.error("Invalid chapter number: %s", chapter_str)
                continue

            chapters.append(
                Chapter(
                    id=f"{manga_id}:{chapter_str}",
                    title="untitled",
                    chapter_num=chapter_num,
                    source=self._source,
                )
            )

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
            ApiError: If chapter_id format is invalid
        """
        try:
            manga_id, chapter_str = chapter_id.split(":", 1)
        except ValueError as e:
            raise ApiError(f"Invalid chapter_id format: {chapter_id}") from e

        variables = CHAPTER_PAGES_QUERY.format(
            manga_id=manga_id,
            chapter_string=chapter_str,
        )
        extensions = json.dumps({"persistedQuery": {"version": 1, "sha256Hash": CHAPTER_HASH}})
        params = {
            "variables": variables,
            "extensions": extensions,
        }

        try:
            response = await self._request(ALLANIME_API_URL, params=params)
            return self._parse_download_resource(response, chapter_id)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error retrieving download resources: %s", e)
            raise

    def _parse_download_resource(self, data: dict, chapter_id: str) -> DownloadResource:
        """Parse chapter pages response into DownloadResource.

        Args:
            data: Raw API response data
            chapter_id: The chapter ID being fetched

        Returns:
            DownloadResource: Processed download resource object

        Raises:
            NotFoundError: If no chapter pages are found or URLs are invalid
        """
        response_data = data.get("data", {})

        if "tobeparsed" in response_data:
            response_data = decode_tobeparsed(response_data["tobeparsed"])

        try:
            chapter_pages = ChapterPagesData.from_dict(response_data.get("chapterPages", {}))
        except ValueError:
            raise NotFoundError(f"No chapter pages found for chapter {chapter_id}")

        if not chapter_pages.edges:
            raise NotFoundError(f"No chapter pages found for chapter {chapter_id}")

        urls = [
            f"{CDN_BASE_URL}{picture.url}"
            for edge in chapter_pages.edges
            for picture in edge.picture_urls
        ]

        if not urls:
            raise NotFoundError(f"No image URLs found for chapter {chapter_id}")

        return DownloadResource(urls=urls, source=self._source)
