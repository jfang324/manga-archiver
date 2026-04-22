import asyncio
from asyncio import Semaphore

from aiohttp import ClientSession


class DownloadError(Exception):
    """Raised when an image download fails."""


DEFAULT_CONCURRENCY: int = 40


class DownloadClient:
    """Client for downloading images from URLs."""

    def __init__(
        self,
        session: ClientSession,
        max_concurrent: int = DEFAULT_CONCURRENCY,
    ) -> None:
        """Initialize the downloader with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
            max_concurrent: Maximum concurrent downloads (default 10)
        """
        self._session = session
        self._semaphore = Semaphore(max_concurrent)

    async def download_image(
        self,
        url: str,
        headers: dict | None = None,
        semaphore: Semaphore | None = None,
    ) -> bytes:
        """Download a single image from the given URL.

        Args:
            url: The URL of the image to download
            headers: Optional headers to include in the request
            semaphore: Optional semaphore for rate limiting (uses default if None)

        Returns:
            bytes: The binary data of the image

        Raises:
            DownloadError: If the download fails
        """
        sem = semaphore or self._semaphore

        async with sem, self._session.get(url, headers=headers, timeout=5) as response:
            if response.status == 200:
                return await response.read()
            raise DownloadError(
                f"Failed to download image from {url}. Status code: {response.status}"
            )

    async def download_images(
        self,
        urls: list[str],
        headers: dict | None = None,
        semaphore: Semaphore | None = None,
    ) -> list[bytes]:
        """Download multiple images concurrently from the given URLs.

        Args:
            urls: The URLs of the images to download
            headers: Optional headers to include in each request
            semaphore: Optional semaphore for rate limiting (uses default if None)

        Returns:
            list[bytes]: List of binary data for each image

        Raises:
            DownloadError: If the download fails
        """
        sem = semaphore or self._semaphore

        tasks = [asyncio.create_task(self.download_image(url, headers, sem)) for url in urls]

        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            raise
