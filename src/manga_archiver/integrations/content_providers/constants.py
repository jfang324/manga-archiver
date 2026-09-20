"""Constants used across multiple providers."""

from ...models import ContentSource

DEFAULT_REQUEST_TIMEOUT: int = 10

ALLMANGA_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://allmanga.to",
    "Referer": "https://allmanga.to/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
}

MKISSA_HEADERS: dict[str, str] = {
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://mkissa.to",
    "Referer": "https://mkissa.to/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-site",
    "User-Agent": (
        "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
        "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
        "Mobile/15E148 Safari/604.1"
    ),
}

API_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: ALLMANGA_HEADERS,
}

CDN_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}
