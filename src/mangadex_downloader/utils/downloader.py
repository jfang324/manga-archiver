"""Generic image download utilities."""

import asyncio

import aiohttp

from ..integrations.exceptions import DownloadError


class DownloadClient:
    """Client for downloading images from URLs.

    Provider-agnostic - works with any image URL.
    """

    def __init__(self, session: aiohttp.ClientSession) -> None:
        """Initialize the downloader with an HTTP session.

        :param session: The aiohttp ClientSession to use for requests
        """
        self._session = session

    async def download_image(self, url: str) -> bytes:
        """Download a single image from the given URL.

        :param url: The URL of the image to download
        :return: The binary data of the image
        :raises DownloadError: If the download fails
        """
        async with self._session.get(url) as response:
            if response.status == 200:
                return await response.read()
            else:
                raise DownloadError(
                    f"Failed to download image from {url}. "
                    f"Status code: {response.status}"
                )

    async def download_images(self, urls: list[str]) -> list[bytes]:
        """Download multiple images concurrently from the given URLs.

        :param urls: The URLs of the images to download
        :return: List of binary data for each image
        """
        tasks = [self.download_image(url) for url in urls]
        try:
            return await asyncio.gather(*tasks)
        except DownloadError as e:
            print(f"Error downloading images: {e}")
            return []
