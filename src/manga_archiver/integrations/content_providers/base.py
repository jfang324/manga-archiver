from abc import ABC, abstractmethod

from aiohttp import ClientSession

from ...types import Chapter, ContentSource, DownloadResource, Manga


class Provider(ABC):
    """Abstract base class for manga provider integrations."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the provider with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
        """
        self._session = session
        self._source: ContentSource

    @property
    def source(self) -> ContentSource:
        """Return the content source this provider handles."""
        return self._source

    @abstractmethod
    async def search_manga(self, query: str, page: int, page_size: int) -> list[Manga]:
        """Search for manga matching the query.

        Args:
            query: The search query string
            page: The page number to fetch
            page_size: Number of results per page

        Returns:
            list[Manga]: List of matching manga objects
        """
        pass

    @abstractmethod
    async def get_chapters(self, manga_id: str) -> list[Chapter]:
        """Retrieve chapters for a given manga.

        Args:
            manga_id: The ID of the manga to get chapters for

        Returns:
            list[Chapter]: List of chapter objects
        """
        pass

    @abstractmethod
    async def get_download_resource(self, chapter_id: str) -> DownloadResource:
        """Get download resource information for a chapter.

        Args:
            chapter_id: The ID of the chapter to get download info for

        Returns:
            DownloadResource: Download resource object containing URLs to the images of the chapter
        """
        pass
