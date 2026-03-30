from abc import ABC, abstractmethod

from aiohttp import ClientSession

from ..types import ProcessedChapter, ProcessedDownloadResource, ProcessedManga


class Provider(ABC):
    """
    Abstract base class for manga provider integrations.
    """

    def __init__(self, session: ClientSession) -> None:
        """
        Initialize the provider with an HTTP session.

        Args:
            session (ClientSession): The aiohttp ClientSession to use for requests
        """
        self._session = session

    @abstractmethod
    async def search_manga(self, query: str) -> list[ProcessedManga]:
        """
        Search for manga matching the query.

        Args:
            query (str): The search query string

        Returns:
            List of matching manga objects
        """
        pass

    @abstractmethod
    async def get_chapters(self, manga_id: str) -> list[ProcessedChapter]:
        """
        Retrieve chapters for a given manga.

        Args:
            manga_id (str): The ID of the manga to get chapters for

        Returns:
            List of chapter objects
        """
        pass

    @abstractmethod
    async def get_download_resource(self, chapter_id: str) -> ProcessedDownloadResource:
        """
        Get download resource information for a chapter.

        Args:
            chapter_id (str): The ID of the chapter to get download info for

        Returns:
            Download resource object containing URLs to the images of the chapter
        """
        pass
