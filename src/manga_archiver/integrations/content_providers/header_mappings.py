"""Maps content sources to required request headers.

For providers that require special headers (e.g., Referer) to access their API or CDN.
"""

from ...types import ContentSource

# Headers required for API requests per provider
API_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}

# Headers required for CDN access per provider (for downloads)
CDN_HEADERS: dict[ContentSource, dict[str, str]] = {
    ContentSource.ALLMANGA: {
        "Referer": "https://allmanga.to/",
        "User-Agent": "Mozilla/5.0",
    },
}
