import asyncio

from aiohttp import ClientSession


class DownloadError(Exception):
    """Raised when an image download fails."""


class DownloadClient:
    """Client for downloading images from URLs."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize the downloader with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
        """
        self._session = session

    async def download_image(self, url: str, headers: dict | None = None) -> bytes:
        """Download a single image from the given URL.

        Args:
            url: The URL of the image to download
            headers: Optional headers to include in the request

        Returns:
            bytes: The binary data of the image

        Raises:
            DownloadError: If the download fails
        """
        async with self._session.get(url, headers=headers, timeout=5) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise DownloadError(
                    f"Failed to download image from {url}. Status code: {response.status}"
                )

    async def download_images(self, urls: list[str], headers: dict | None = None) -> list[bytes]:
        """Download multiple images concurrently from the given URLs.

        Args:
            urls: The URLs of the images to download
            headers: Optional headers to include in each request

        Returns:
            list[bytes]: List of binary data for each image

        Raises:
            DownloadError: If the download fails
        """
        tasks = [asyncio.create_task(self.download_image(url, headers)) for url in urls]

        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            raise
