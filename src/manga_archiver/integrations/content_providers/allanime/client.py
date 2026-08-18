import json

from aiohttp import ClientSession

from ....models import Chapter, ContentSource, DownloadResource, Manga
from ...exceptions import ApiError, BadGatewayError, NotFoundError, RateLimitError
from ..base import Provider
from ..constants import API_HEADERS, DEFAULT_REQUEST_TIMEOUT, MKISSA_HEADERS
from .constants import (
    ALLANIME_API_URL,
    CDN_BASE_URL,
    CHAPTER_PAGES_LANE,
    CHAPTER_PAGES_QUERY,
    MANGA_DETAILS_QUERY,
    PERSISTED_QUERY_NOT_FOUND,
    SEARCH_QUERY,
    STALE_CRYPTO_MESSAGE,
    PersistedQueryName,
)
from .decode import decode_tobeparsed
from .keygen import KeygenService
from .types import AllMangaChapterResponse, AllMangaSearchResponse, DownloadResourceResponse


def _build_query_params(variables: str, query_hash: str, aa_req: str) -> dict:
    """Build the URL params for a persisted GraphQL query with an aaReq token."""
    return {
        "variables": variables,
        "extensions": json.dumps(
            {
                "persistedQuery": {"version": 1, "sha256Hash": query_hash},
                "aaReq": aa_req,
                "k": CHAPTER_PAGES_LANE,
            }
        ),
    }


def _build_request_headers(build_id: str, headers: dict | None) -> dict:
    """Merge provider headers with the build id the aaReq token was minted with."""
    return {**(headers or API_HEADERS.get(ContentSource.ALLMANGA, {})), "x-build-id": build_id}


class AllMangaClient(Provider):
    """Client for interacting with the AllManga API."""

    def __init__(self, session: ClientSession) -> None:
        """Initialize AllManga client with HTTP session.

        Args:
            session: The session used for API requests
        """
        super().__init__(session)
        self._source = ContentSource.ALLMANGA
        self._keygen = KeygenService(session)

    async def _request(
        self, url: str, params: dict | None = None, headers: dict | None = None
    ) -> dict:
        """Make API request with optional custom headers.

        Args:
            url: API endpoint URL
            params: Query parameters for GraphQL request
            headers: Custom request headers (falls back to API_HEADERS)

        Returns:
            dict: JSON response as a dictionary

        Raises:
            NotFoundError: 404 response
            RateLimitError: 429 response
            BadGatewayError: 502 response
            ApiError: Other error status codes
        """
        request_headers = headers or API_HEADERS.get(ContentSource.ALLMANGA, {})

        async with self._session.get(
            url, params=params, headers=request_headers, timeout=DEFAULT_REQUEST_TIMEOUT
        ) as response:
            if response.status == 404:
                raise NotFoundError(f"Resource not found: {url}")

            if response.status == 429:
                raise RateLimitError(f"Rate limit exceeded for: {url}")

            if response.status == 502:
                raise BadGatewayError(f"Bad gateway error: {url}")

            if response.status != 200:
                raise ApiError(f"API error: {url} returned status {response.status}")

            return await response.json()

    def _validate_response(self, response: dict) -> dict:
        """Validate an API response and return it for parsing.

        Centralizes the API error envelope so parsers can rely on a
        well-formed response: stale crypto or unregistered persisted queries
        drop the keygen cache and surface as a RateLimitError, other GraphQL
        errors surface as an ApiError, and a missing data payload is rejected.

        Args:
            response: Raw API response

        Returns:
            dict: The validated response

        Raises:
            RateLimitError: API reported stale crypto or query not found
            ApiError: Any other error shape or a missing data payload
        """
        errors = response.get("errors")
        if isinstance(errors, list) and errors and isinstance(errors[0], dict):
            message = errors[0].get("message")
            if isinstance(message, str):
                if message in (STALE_CRYPTO_MESSAGE, PERSISTED_QUERY_NOT_FOUND):
                    # The API may have rotated crypto values or registered
                    # persisted query hashes, so drop the cache and surface a
                    # rate-limit style error for the caller to retry later.
                    self._keygen.invalidate()
                    raise RateLimitError(f"API reports rotated keygen values: {errors}")
                raise ApiError(f"API error: {message}")

        data = response.get("data")
        if not isinstance(data, dict):
            raise ApiError("Invalid response: data is not a dict")

        return response

    async def _generate_aa_req(self, query: PersistedQueryName) -> tuple[str, str, str]:
        """Build the aaReq token, build id, and query hash for a persisted query.

        Args:
            query: Persisted query to build the token for

        Returns:
            tuple[str, str, str]: (query_hash, aaReq token, build_id)

        Raises:
            ApiError: If the current keygen values cannot produce a valid token
        """
        try:
            query_hash = await self._keygen.query_hash(query)
            aa_req, build_id = await self._keygen.build_aa_req(query_hash, CHAPTER_PAGES_LANE)
            return query_hash, aa_req, build_id
        except ValueError as e:
            raise ApiError(f"Failed to generate aaReq token: {e}") from e

    async def search_manga(self, query: str, page: int, page_size: int) -> list[Manga]:
        """Search for manga matching query with pagination.

        Args:
            query: Search query string
            page: Page number to fetch (1-indexed)
            page_size: Results per page (max 20 per API limits)

        Returns:
            list[Manga]: List of matching manga objects

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            BadGatewayError: If the API is temporarily unavailable (502)
            ApiError: If the API returns any other error
        """
        variables = SEARCH_QUERY.format(
            query=query,
            limit=page_size,
            page=page,
        )
        query_hash, aa_req, build_id = await self._generate_aa_req(PersistedQueryName.SEARCH)
        response = await self._request(
            ALLANIME_API_URL,
            params=_build_query_params(variables, query_hash, aa_req),
            headers=_build_request_headers(build_id, None),
        )

        return self._parse_search_response(self._validate_response(response))

    def _parse_search_response(self, response: dict) -> list[Manga]:
        """Parse search response into Manga objects.

        Args:
            response: Validated API response data

        Returns:
            list[Manga]: List of processed manga objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = AllMangaSearchResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        return [
            Manga(id=result._id, title=result.title, source=self._source)
            for result in raw_data.data.edges
        ]

    async def get_chapters(self, manga_id: str) -> list[Chapter]:
        """Retrieve all chapters for a manga.

        Args:
            manga_id: AllManga manga ID

        Returns:
            list[Chapter]: List of chapter objects sorted by chapter number

        Raises:
            NotFoundError: If the resource is not found (404)
            RateLimitError: If rate limited (429)
            BadGatewayError: If the API is temporarily unavailable (502)
            ApiError: If the API returns any other error
        """
        variables = MANGA_DETAILS_QUERY.format(manga_id=manga_id)
        query_hash, aa_req, build_id = await self._generate_aa_req(PersistedQueryName.MANGA)
        response = await self._request(
            ALLANIME_API_URL,
            params=_build_query_params(variables, query_hash, aa_req),
            headers=_build_request_headers(build_id, None),
        )

        return self._parse_chapter_data(self._validate_response(response), manga_id)

    def _parse_chapter_data(self, response: dict, manga_id: str) -> list[Chapter]:
        """Parse manga details response into Chapter objects.

        Args:
            response: Validated API response data
            manga_id: AllManga manga ID

        Returns:
            list[Chapter]: List of processed chapter objects

        Raises:
            ApiError: If response is missing required data
        """
        try:
            raw_data = AllMangaChapterResponse.from_dict(response)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        chapters: list[Chapter] = [
            Chapter(
                id=f"{manga_id}:{chapter_num:g}",
                title="untitled",
                chapter_num=chapter_num,
                source=self._source,
            )
            for chapter_num in raw_data.data.detail.sub
        ]

        chapters.sort(key=lambda x: x.chapter_num)
        return chapters

    async def get_download_resource(self, chapter_id: str) -> DownloadResource:
        """Get image URLs for downloading a chapter.

        Args:
            chapter_id: Format "manga_id:chapter_string"

        Returns:
            DownloadResource: Download resource object containing URLs

        Raises:
            NotFoundError: If the chapter is not found
            RateLimitError: If the API rate limit is exceeded
            ApiError: If the API returns any other error
            ValueError: If chapter_id format is invalid
        """
        try:
            manga_id, chapter_str = chapter_id.split(":", 1)
        except ValueError as e:
            raise ValueError(f"Invalid chapter_id format: {chapter_id}") from e

        if not manga_id or not chapter_str:
            raise ValueError(f"Invalid chapter_id format: {chapter_id}")

        variables = CHAPTER_PAGES_QUERY.format(
            manga_id=manga_id,
            chapter_string=chapter_str,
        )
        query_hash, aa_req, build_id = await self._generate_aa_req(PersistedQueryName.CHAPTER)
        response = await self._request(
            ALLANIME_API_URL,
            params=_build_query_params(variables, query_hash, aa_req),
            headers=_build_request_headers(build_id, MKISSA_HEADERS),
        )

        return await self._parse_download_resource(self._validate_response(response), chapter_id)

    async def _parse_download_resource(self, response: dict, chapter_id: str) -> DownloadResource:
        """Parse chapter pages response into DownloadResource.

        Args:
            response: Validated API response data
            chapter_id: The chapter ID being fetched

        Returns:
            DownloadResource: Processed download resource object

        Raises:
            ApiError: If response data is invalid or no URLs found
        """
        response_data = response["data"]
        if not isinstance(response_data, dict):
            raise ApiError("Invalid response: data is not a dict")

        if "tobeparsed" in response_data:
            keygen = await self._keygen.get()
            try:
                response_data = decode_tobeparsed(
                    response_data["tobeparsed"], CHAPTER_PAGES_LANE, keygen
                )
            except ValueError as e:
                # Response-encryption keys may have rotated mid-TTL; drop the
                # cache so the next request re-fetches keygen instead of
                # retrying the stale values for the rest of the TTL.
                self._keygen.invalidate()
                raise ApiError(str(e)) from e

        try:
            download_response = DownloadResourceResponse.from_dict(response_data)
        except ValueError as e:
            raise ApiError(f"Invalid response: {e}") from e

        urls = [
            f"{CDN_BASE_URL}{picture.url}"
            for edge in download_response.pages.edges
            for picture in edge.picture_urls
            if picture.url and picture.url.strip()
        ]

        if not urls:
            raise ApiError(f"No image URLs found for chapter {chapter_id}")

        return DownloadResource(urls=urls, source=self._source)
