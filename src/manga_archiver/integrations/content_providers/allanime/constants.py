ALLANIME_API_URL: str = "https://api.allanime.day/api"

# GraphQL persisted query hashes (from reverse-engineered API)
SEARCH_HASH: str = "2d48e19fb67ddcac42fbb885204b6abb0a84f406f15ef83f36de4a66f49f651a"
MANGA_HASH: str = "d77781dcf964b97aea0be621dbde430e89e200b58526823ee6010dd11c3ca96a"
CHAPTER_HASH: str = "a062f1b131dae3d17c1950fad14640d066b988ac10347ed49cfbe70f5e7f661b"

# CDN base URL for image downloads
CDN_BASE_URL: str = "https://ytimgf.youtube-anime.com/"

# Query templates
SEARCH_QUERY = '{{"search": {{"query": "{query}", "sortBy": "Name_ASC", "isManga": true}}, "limit": {limit}, "page": {page}, "translationType": "sub", "countryOrigin": "ALL"}}'
MANGA_DETAILS_QUERY = (
    '{{"_id": "{manga_id}", "search": {{"allowAdult": false, "allowUnknown": false}}}}'
)
CHAPTER_PAGES_QUERY = '{{"mangaId": "{manga_id}", "translationType": "sub", "chapterString": "{chapter_string}", "limit": 10, "offset": 0}}'
