import asyncio
import logging

from aiohttp import ClientSession

from ..integrations import DownloadError

logger = logging.getLogger(__name__)


class DownloadClient:
    """
    Client for downloading images from URLs.
    """

    def __init__(self, session: ClientSession) -> None:
        """
        Initialize the downloader with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
        """
        self._session = session

    async def download_image(self, url: str) -> bytes:
        """
        Download a single image from the given URL.

        Args:
            url: The URL of the image to download

        Returns:
            bytes: The binary data of the image

        Raises:
            DownloadError: If the download fails
        """
        async with self._session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                logger.error(
                    "Failed to download image from %s. Status code: %s",
                    url,
                    response.status,
                )
                raise DownloadError(
                    f"Failed to download image from {url}. "
                    f"Status code: {response.status}"
                )

    async def download_images(self, urls: list[str]) -> list[bytes]:
        """
        Download multiple images concurrently from the given URLs.

        Args:
            urls: The URLs of the images to download

        Returns:
            List of binary data for each image

        Raises:
            DownloadError: If the download fails
        """
        tasks = [asyncio.create_task(self.download_image(url)) for url in urls]

        try:
            return await asyncio.gather(*tasks)
        except Exception as e:
            logger.error("Error downloading images: %s", e)

            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)

            raise
