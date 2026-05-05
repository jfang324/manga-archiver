import asyncio

from aiohttp import ClientSession

from ..integrations.exceptions import BadGatewayError, NotFoundError, RateLimitError
from .adaptive_limiter import AdaptiveLimiter

MAX_RETRIES: int = 3
BASE_DELAY: int = 2


class DownloadError(Exception):
    """Raised when an image download fails."""


class DownloadClient:
    """Client for downloading images from URLs."""

    def __init__(
        self,
        session: ClientSession,
    ) -> None:
        """Initialize the downloader with an HTTP session.

        Args:
            session: The aiohttp ClientSession to use for requests
        """
        self._session = session

    async def download_image(
        self,
        url: str,
        limiter: AdaptiveLimiter,
        headers: dict | None = None,
    ) -> bytes:
        """Download a single image from the given URL.

        Args:
            url: The URL of the image to download
            limiter: Limiter for rate limiting
            headers: Optional headers to include in the request

        Returns:
            bytes: The binary data of the image

        Raises:
            NotFoundError: If the image is not found
            RateLimitError: If the API rate limit is exceeded
            BadGatewayError: If the API is temporarily unavailable
            DownloadError: If the download fails
        """
        async with (
            limiter.acquire(),
            self._session.get(url, headers=headers, timeout=5) as response,
        ):
            if response.status == 200:
                return await response.read()

            if response.status == 404:
                raise NotFoundError(f"Image not found: {url}")

            if response.status == 429:
                raise RateLimitError(f"Rate limited: {url}")

            if response.status == 502:
                raise BadGatewayError(f"Bad gateway: {url}")

            raise DownloadError(
                f"Failed to download image from {url}. Status code: {response.status}"
            )

    async def _download_with_retry(
        self,
        url: str,
        headers: dict | None,
        limiter: AdaptiveLimiter,
    ) -> bytes:
        """Download a single image with retry logic for transient errors.

        Args:
            url: The URL of the image to download
            headers: Optional headers to include in the request
            limiter: The limiter for concurrency control

        Returns:
            bytes: The binary data of the image

        Raises:
            NotFoundError: If the image is not found
            DownloadError: If download fails with a non-retryable error
            RuntimeError: If download fails after all retries
        """
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:  # PERF203: Retry loop is intentional for transient errors
                image_data = await self.download_image(url, limiter, headers)
                if attempt == 0:
                    await limiter.record_success()

                return image_data
            except (RateLimitError, BadGatewayError) as e:  # noqa: PERF203
                last_error = e
                await limiter.record_retryable_error()

                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(BASE_DELAY * (2**attempt))
            except NotFoundError:
                raise
            except DownloadError:
                raise

        raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts") from last_error

    async def download_images(
        self,
        urls: list[str],
        limiter: AdaptiveLimiter,
        headers: dict | None = None,
    ) -> list[bytes]:
        """Download multiple images concurrently from the given URLs.

        Args:
            urls: The URLs of the images to download
            limiter: Limiter for rate limiting
            headers: Optional headers to include in each request

        Returns:
            list[bytes]: List of binary data for each image

        Raises:
            DownloadError: If the download fails
        """
        tasks = [
            asyncio.create_task(self._download_with_retry(url, headers, limiter)) for url in urls
        ]

        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            raise
