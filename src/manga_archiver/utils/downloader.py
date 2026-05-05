import asyncio

from aiohttp import ClientSession

from ..integrations.exceptions import BadGatewayError, NotFoundError, RateLimitError
from .download_limiter import DownloadLimiter, StaticDownloadLimiter

DEFAULT_CONCURRENCY: int = 40

MAX_RETRIES: int = 3
BASE_DELAY: int = 2


class DownloadError(Exception):
    """Raised when an image download fails."""


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
            max_concurrent: Maximum concurrent downloads (default 40)

        Raises:
            ValueError: If max_concurrent is less than 1
        """
        if max_concurrent < 1:
            raise ValueError("max_concurrent must be greater than 0")

        self._session = session
        self._limiter = StaticDownloadLimiter(max_concurrent)

    async def download_image(
        self,
        url: str,
        headers: dict | None = None,
        limiter: DownloadLimiter | None = None,
    ) -> bytes:
        """Download a single image from the given URL.

        Args:
            url: The URL of the image to download
            headers: Optional headers to include in the request
            limiter: Optional limiter for rate limiting (uses default if None)

        Returns:
            bytes: The binary data of the image

        Raises:
            NotFoundError: If the image is not found
            RateLimitError: If the API rate limit is exceeded
            BadGatewayError: If the API is temporarily unavailable
            DownloadError: If the download fails
        """
        download_limiter = limiter or self._limiter

        async with (
            download_limiter.acquire(),
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
        limiter: DownloadLimiter,
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
                return await self.download_image(url, headers, limiter)
            except (RateLimitError, BadGatewayError) as e:  # noqa: PERF203
                last_error = e

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
        headers: dict | None = None,
        limiter: DownloadLimiter | None = None,
    ) -> list[bytes]:
        """Download multiple images concurrently from the given URLs.

        Args:
            urls: The URLs of the images to download
            headers: Optional headers to include in each request
            limiter: Optional limiter for rate limiting (uses default if None)

        Returns:
            list[bytes]: List of binary data for each image

        Raises:
            DownloadError: If the download fails
        """
        download_limiter = limiter or self._limiter

        tasks = [
            asyncio.create_task(self._download_with_retry(url, headers, download_limiter))
            for url in urls
        ]

        try:
            return await asyncio.gather(*tasks)
        except Exception:
            for task in tasks:
                task.cancel()

            await asyncio.gather(*tasks, return_exceptions=True)
            raise
