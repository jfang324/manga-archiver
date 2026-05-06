"""Constants used across multiple providers."""

from ...models import ContentSource

DEFAULT_REQUEST_TIMEOUT: int = 10

API_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Accept": "*/*",
        "Accept-Language": "en-US,en;q=0.9",
        "Origin": "https://allmanga.to",
        "Referer": "https://allmanga.to/",
        "User-Agent": (
            "Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) "
            "AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 "
            "Mobile/15E148 Safari/604.1"
        ),
    },
}

CDN_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}
