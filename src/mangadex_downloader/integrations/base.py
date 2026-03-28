from abc import ABC, abstractmethod

import aiohttp

from ..types import ProcessedChapter, ProcessedDownloadResource, ProcessedManga


class Provider(ABC):
    """
    Abstract base class for manga provider integrations.

    Defines the interface that all provider implementations must follow.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """
        Initialize the provider with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
        """
        self._session = session

    @abstractmethod
    async def search_manga(self, query: str) -> list[ProcessedManga]:
        """Search for manga matching the query.

        Args:
            query: The search query string

        Returns:
            List of matching manga objects
        """
        pass

    @abstractmethod
    async def get_chapters(self, manga_id: str) -> list[ProcessedChapter]:
        """Retrieve chapters for a given manga.

        Args:
            manga_id: The ID of the manga to get chapters for

        Returns:
            List of chapter objects
        """
        pass

    @abstractmethod
    async def get_download_resource(self, chapter_id: str) -> ProcessedDownloadResource:
        """Get download resource information for a chapter.

        Args:
            chapter_id: The ID of the chapter to get download info for

        Returns:
            Download resource object containing URLs
        """
        pass
