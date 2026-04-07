import logging

from aiohttp import ClientSession

from ....types import ProcessedChapter, ProcessedDownloadResource, ProcessedManga
from ...exceptions import ApiError, NotFoundError, RateLimitError
from ..base import Provider
from .constants import MANGADEX_RESOURCE_LINKS_URL, MANGADEX_ROOT_URL

logger = logging.getLogger(__name__)


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
            data_saver: Whether to download lower quality images. Defaults to False
        """
        super().__init__(session)

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
        async with self._session.get(url, params=params) as response:
            if response.status == 404:
                raise NotFoundError(f"Resource not found: {url}")

            if response.status == 429:
                raise RateLimitError(f"Rate limit exceeded for: {url}")

            if response.status != 200:
                raise ApiError(f"API error: {url} returned status {response.status}")

            return await response.json()

    @staticmethod
    def _get_nested(data: dict, *keys: str, default: str = "") -> str:
        """
        Safely traverse nested dictionaries.

        Args:
            data: The dictionary to traverse
            keys: The sequence of keys to follow
            default: Value to return if any key is missing. Defaults to ""

        Returns:
            str: The found value or default
        """
        result: dict | str | None = data

        for key in keys:
            if isinstance(result, dict):
                result = result.get(key)
            else:
                return default

            if result is None:
                return default

        if isinstance(result, str):
            return result

        if isinstance(result, dict) and result:
            return next(iter(result.values()), default)

        return default

    async def search_manga(self, query: str) -> list[ProcessedManga]:
        """
        Search for manga matching the query.

        Args:
            query: The search query string

        Returns:
            list[ProcessedManga]: List of matching manga objects

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            ApiError: If the API returns any other error
        """
        url: str = f"{MANGADEX_ROOT_URL}?title={query}"
        params: dict = {"limit": 100}

        try:
            response: dict = await self._request(url, params)

            return self._process_manga_data(response)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error searching manga: %s", e)
            raise

    def _process_manga_data(self, manga_data: dict) -> list[ProcessedManga]:
        """
        Process raw manga data into ProcessedManga objects.

        Args:
            manga_data: Raw API response data

        Returns:
            list[ProcessedManga]: List of processed manga objects
        """
        processed_manga_data: list[ProcessedManga] = []
        data: list[dict] = manga_data.get("data", [])

        for element in data:
            if "id" in element:
                attributes = element.get("attributes", {})
                title = (
                    self._get_nested(attributes, "title", "en")
                    or self._get_nested(attributes, "title")
                    or "Unknown"
                )
                id = element["id"]

                manga = ProcessedManga(title=title, id=id)
                processed_manga_data.append(manga)

        return processed_manga_data

    async def get_chapters(self, manga_id: str) -> list[ProcessedChapter]:
        """
        Retrieve chapters for a given manga.

        Args:
            manga_id: The ID of the manga to get chapters for

        Returns:
            list[ProcessedChapter]: List of chapter objects sorted by chapter number

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

        try:
            response: dict = await self._request(url, params)

            return self._process_chapter_data(response)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error retrieving chapters: %s", e)
            raise

    def _process_chapter_data(self, chapter_data: dict) -> list[ProcessedChapter]:
        """
        Process raw chapter data into ProcessedChapter objects.

        Args:
            chapter_data: Raw API response data

        Returns:
            list[ProcessedChapter]: List of processed chapter objects
        """
        processed_chapter_data: list[ProcessedChapter] = []
        data: list[dict] = chapter_data.get("data", [])
        already_contains: set[str] = set()

        for element in data:
            if "id" in element:
                attributes = element.get("attributes", {})
                title: str = attributes.get("title", "")
                chapter: str = attributes.get("chapter", "0")

                if chapter not in already_contains:
                    already_contains.add(chapter)
                    processed_chapter_data.append(
                        ProcessedChapter(title=title, id=element["id"], chapter=chapter)
                    )

        processed_chapter_data.sort(key=lambda x: float(x["chapter"]))
        return processed_chapter_data

    async def get_download_resource(self, chapter_id: str) -> ProcessedDownloadResource:
        """
        Get download resource information for a chapter.

        Args:
            chapter_id: The ID of the chapter to get download info for

        Returns:
            ProcessedDownloadResource: Download resource object containing URLs

        Raises:
            NotFoundError: If the chapter is not found
            RateLimitError: If the API rate limit is exceeded
            ApiError: If the API returns any other error
        """
        url: str = f"{MANGADEX_RESOURCE_LINKS_URL}/{chapter_id}"

        try:
            response: dict = await self._request(url)

            return self._process_download_resource_data(response)
        except (NotFoundError, RateLimitError, ApiError) as e:
            logger.error("Error retrieving download resources: %s", e)
            raise

    def _process_download_resource_data(
        self, download_resources: dict
    ) -> ProcessedDownloadResource:
        """
        Process raw download resource data into ProcessedDownloadResource.

        Args:
            download_resources: Raw API response data

        Returns:
            ProcessedDownloadResource: Processed download resource object
        """
        download_urls: list[str] = []
        base_url: str = download_resources["baseUrl"]
        url_hash: str = download_resources["chapter"]["hash"]

        # Use data-saver if requested and available, otherwise fall back to data
        chapter_data = download_resources["chapter"]
        if self._data_saver and "dataSaver" in chapter_data:
            file_list_key = "dataSaver"
            url_quality = "data-saver"
        else:
            file_list_key = "data"
            url_quality = "data"

        for element in chapter_data[file_list_key]:
            download_urls.append(f"{base_url}/{url_quality}/{url_hash}/{element}")

        return ProcessedDownloadResource(urls=download_urls, hash=url_hash)
