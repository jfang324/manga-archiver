from enum import Enum

ALLANIME_API_URL: str = "https://api.mkissa.net/api"
KEYGEN_URL: str = (
    "https://raw.githubusercontent.com/jfang324/manga-archiver-keygen/main/keygen.json"
)
BROWSER_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# GraphQL persisted query hashes (sha256 of the site bundle's query documents).
# Live values come from keygen.json query_hashes; these are the offline fallback.
SEARCH_HASH: str = "6aa0ec525141123d2a64012a5ace12ba1cdef2f47d12abfec62158f3a7c73f5f"
MANGA_HASH: str = "97db525f763de75fd165a3dfd4bf6570adaa914a327ebd3cda0bd703e92de758"
CHAPTER_HASH: str = "9c06f42995949a3b6e15e843d7832668f4460416ba94881a2cdb9a906266ad40"


class PersistedQueryName(Enum):
    """Persisted GraphQL queries the AllManga API serves by registered hash."""

    SEARCH = "search"
    MANGA = "manga"
    CHAPTER = "chapter"


PERSISTED_QUERY_HASH_FALLBACKS: dict[PersistedQueryName, str] = {
    PersistedQueryName.SEARCH: SEARCH_HASH,
    PersistedQueryName.MANGA: MANGA_HASH,
    PersistedQueryName.CHAPTER: CHAPTER_HASH,
}


# AllAnime aaReq crypto keygen fallback (refreshed periodically from manga-archiver-keygen)
ALLANIME_FALLBACK_BUILD_ID: str = "96"
ALLANIME_FALLBACK_EPOCH: int = 2953
ALLANIME_FALLBACK_LANES: dict[str, str] = {
    # episode
    "k7": "695af2782a31edc2c99a8b21a781d535fb0eab3b8574647f03931d3c3bed5f16",
    # chapter pages
    "k9": "e81105a3132d3e97c05a95f1484d33f53e0316ab9a23387a717fa3e749c6aba3",
    # music
    "k2": "76b070b0e9192f85e8c8901c33003c07b43d094225b35019c10541b254cb5683",
}
RESPONSE_STATIC_KEY_SEED: str = "Xot36i3lK3:v1"
CRYPTO_TTL_SECONDS: int = 300

# Content lane for chapter-pages crypto (from the site's lane constants)
CHAPTER_PAGES_LANE: str = "k9"

# Error message the API returns when the aaReq token was built with rotated-out crypto values
STALE_CRYPTO_MESSAGE: str = "AA_CRYPTO_STALE"

# Error message the API returns when a persisted query hash is not registered
PERSISTED_QUERY_NOT_FOUND: str = "PersistedQueryNotFound"

# CDN base URL for image downloads
CDN_BASE_URL: str = "https://ytimgf.youtube-anime.com/"

# Query templates
SEARCH_QUERY = '{{"search": {{"query": "{query}", "sortBy": "Name_ASC", "isManga": true}}, "limit": {limit}, "page": {page}, "translationType": "sub", "countryOrigin": "ALL"}}'
MANGA_DETAILS_QUERY = (
    '{{"_id": "{manga_id}", "search": {{"allowAdult": false, "allowUnknown": false}}}}'
)
CHAPTER_PAGES_QUERY = '{{"mangaId": "{manga_id}", "translationType": "sub", "chapterString": "{chapter_string}", "limit": 10, "offset": 0}}'
