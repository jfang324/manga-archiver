ALLANIME_API_URL: str = "https://api.allanime.day/api"
BUILD_ID: str = "47"
BOOTSTRAP_URL: str = "https://api.mkissa.net/client-crypto/v1/bootstrap"
BROWSER_UA: str = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)
MKISSA_URL: str = "https://mkissa.to/"
CDN_IMMUTABLE: str = "https://cdn.allanime.day/all/mk/_app/immutable/"

# GraphQL persisted query hashes (from reverse-engineered API)
SEARCH_HASH: str = "2d48e19fb67ddcac42fbb885204b6abb0a84f406f15ef83f36de4a66f49f651a"
MANGA_HASH: str = "d77781dcf964b97aea0be621dbde430e89e200b58526823ee6010dd11c3ca96a"
CHAPTER_HASH: str = "404980504d680671d1639cf9a33b1847865c855a32ceaeef900b838896c00464"

# AllAnime aaReq crypto constants (refreshed periodically)
ALLANIME_FALLBACK_EPOCH: int = 4130
ALLANIME_FALLBACK_MASK: str = "b5aa3f32a24c324a81e3ab5b35d35f9111ca1c39eb26d40a1ad76a37c5d956b9"
ALLANIME_FALLBACK_PART_B: str = "eu1Ih9XG2JYVqkp8XDkLObTgxG+mY1TqWWBM6fT21eU="
RESPONSE_STATIC_KEY_SEED: str = "Xot36i3lK3:v1"
CRYPTO_TTL_SECONDS: int = 300
SCRAPE_TIMEOUT_SECONDS: int = 30

# Error message the API returns when the aaReq token was built with rotated-out crypto values
STALE_CRYPTO_MESSAGE: str = "AA_CRYPTO_STALE"

# CDN base URL for image downloads
CDN_BASE_URL: str = "https://ytimgf.youtube-anime.com/"

# Query templates
SEARCH_QUERY = '{{"search": {{"query": "{query}", "sortBy": "Name_ASC", "isManga": true}}, "limit": {limit}, "page": {page}, "translationType": "sub", "countryOrigin": "ALL"}}'
MANGA_DETAILS_QUERY = (
    '{{"_id": "{manga_id}", "search": {{"allowAdult": false, "allowUnknown": false}}}}'
)
CHAPTER_PAGES_QUERY = '{{"mangaId": "{manga_id}", "translationType": "sub", "chapterString": "{chapter_string}", "limit": 10, "offset": 0}}'
