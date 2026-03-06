"""MangaDex API client implementation."""

from typing import Optional, Union

import aiohttp

from ...types import ProcessedChapter, ProcessedDownloadResource, ProcessedManga
from ..base import Provider
from ..exceptions import ApiError, NotFoundError, RateLimitError
from .constants import MANGADEX_RESOURCE_LINKS_URL, MANGADEX_ROOT_URL


class MangaDexApiClient(Provider):
    """Client for interacting with the MangaDex API.

    Implements the Provider interface and handles all MangaDex-specific logic.
    """

    def __init__(
        self,
        session: aiohttp.ClientSession,
        data_saver: bool = False,
    ) -> None:
        """Initialize the MangaDex API client.

        :param session: The aiohttp ClientSession to use for requests
        :param data_saver: Whether to download data-saver (lower quality) images
        """
        super().__init__(session)
        self._data_saver = data_saver

    async def _request(self, url: str, params: Optional[dict] = None) -> dict:
        """Make an HTTP request and return the JSON response.

        :param url: The URL to request
        :param params: Optional query parameters
        :return: The JSON response as a dictionary
        :raises NotFoundError: If the resource is not found (404)
        :raises RateLimitError: If rate limited (429)
        :raises ApiError: For other API errors
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
        """Safely traverse nested dictionaries.

        :param data: The dictionary to traverse
        :param keys: The sequence of keys to follow
        :param default: Value to return if any key is missing
        :return: The found value or default
        """
        result: Union[dict, str, None] = data
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
        """Search for manga matching the query.

        :param query: The search query string
        :return: List of matching manga objects
        """
        url: str = f"{MANGADEX_ROOT_URL}?title={query}"
        params: dict = {"limit": 100}

        try:
            response: dict = await self._request(url, params)
            return self._process_manga_data(response)
        except ApiError as e:
            print(f"Error searching manga: {e}")
            return []

    def _process_manga_data(self, manga_data: dict) -> list[ProcessedManga]:
        """Process raw manga data into ProcessedManga objects.

        :param manga_data: Raw API response data
        :return: List of processed manga objects
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
                manga: ProcessedManga = {
                    "title": title,
                    "id": element["id"],
                }
                processed_manga_data.append(manga)

        return processed_manga_data

    async def get_chapters(self, manga_id: str) -> list[ProcessedChapter]:
        """Retrieve chapters for a given manga.

        :param manga_id: The ID of the manga to get chapters for
        :return: List of chapter objects sorted by chapter number
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
        except ApiError as e:
            print(f"Error retrieving chapters: {e}")
            return []

    def _process_chapter_data(self, chapter_data: dict) -> list[ProcessedChapter]:
        """Process raw chapter data into ProcessedChapter objects.

        :param chapter_data: Raw API response data
        :return: List of processed chapter objects
        """
        processed_chapter_data: list[ProcessedChapter] = []
        data: list[dict] = chapter_data.get("data", [])
        already_contains: set[str] = set()

        for element in data:
            if "id" in element:
                attributes = element.get("attributes", {})
                title: Optional[str] = attributes.get("title")
                chapter: str = (
                    attributes.get("chapter")
                    if attributes.get("chapter") is not None
                    else "0"
                )

                if chapter not in already_contains:
                    already_contains.add(chapter)
                    processed_chapter_data.append(
                        {
                            "title": title,
                            "id": element["id"],
                            "chapter": chapter,
                        }
                    )

        processed_chapter_data.sort(key=lambda x: float(x["chapter"]))
        return processed_chapter_data

    async def get_download_resource(self, chapter_id: str) -> ProcessedDownloadResource:
        """Get download resource information for a chapter.

        :param chapter_id: The ID of the chapter to get download info for
        :return: Download resource object containing URLs
        :raises NotFoundError: If the chapter is not found
        """
        url: str = f"{MANGADEX_RESOURCE_LINKS_URL}/{chapter_id}"

        try:
            response: dict = await self._request(url)
            return self._process_download_resource_data(response)
        except NotFoundError:
            raise
        except ApiError as e:
            raise ApiError(f"Error retrieving download resources: {e}") from e

    def _process_download_resource_data(
        self, download_resources: dict
    ) -> ProcessedDownloadResource:
        """Process raw download resource data into ProcessedDownloadResource.

        :param download_resources: Raw API response data
        :return: Processed download resource object
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

        return {
            "urls": download_urls,
            "hash": url_hash,
        }
