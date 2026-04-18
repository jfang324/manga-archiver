"""Constants used across multiple providers."""

from ...models import ContentSource

DEFAULT_REQUEST_TIMEOUT: int = 10

API_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}

CDN_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}
