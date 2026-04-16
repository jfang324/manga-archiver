"""Mock data for AllManga API unit tests."""

from src.manga_archiver.types import Chapter, ContentSource, DownloadResource, Manga

# Search response data (from example_search_response.json)
mock_search_response: dict = {
    "data": {
        "mangas": {
            "pageInfo": {"total": 196113},
            "edges": [
                {
                    "_id": "PBouNk6dWWBuswfX7",
                    "name": "Jujutsu Kaisen Modulo",
                    "englishName": "Jujutsu Kaisen Modulo",
                    "nativeName": "咒術廻戦≡〈モジュロ〉",
                    "thumbnail": "mcovers/m_tbs/hw2T7NhKcyjsuNZFA/002.jpg",
                    "lastChapterInfo": {
                        "sub": {"chapterString": "25", "pictureUrlsProcessed": 19},
                        "raw": {},
                    },
                    "lastChapterDate": {
                        "sub": {
                            "year": 2026,
                            "month": 2,
                            "date": 5,
                            "minute": 58,
                            "hour": 19,
                        },
                        "raw": {},
                    },
                    "availableChapters": {"sub": 25, "raw": 0},
                    "countryOfOrigin": "JP",
                }
            ],
        }
    }
}

mock_processed_search_results: list[Manga] = [
    Manga(
        id="PBouNk6dWWBuswfX7",
        title="Jujutsu Kaisen Modulo",
        source=ContentSource.ALLMANGA,
    )
]

mock_search_response_empty: dict = {"data": {"mangas": {"pageInfo": {"total": 0}, "edges": []}}}

mock_search_response_no_english_name: dict = {
    "data": {
        "mangas": {
            "pageInfo": {"total": 1},
            "edges": [{"_id": "test123", "name": "Native Name Only", "englishName": None}],
        }
    }
}

mock_search_response_missing_ids: dict = {
    "data": {
        "mangas": {
            "pageInfo": {"total": 2},
            "edges": [{"name": "No ID"}, {"_id": "valid", "name": "Valid"}],
        }
    }
}

# Chapter fetching data (from example_manga_response.json partial)
mock_manga_details_response: dict = {
    "data": {
        "manga": {
            "_id": "PBouNk6dWWBuswfX7",
            "name": "Jujutsu Kaisen Modulo",
            "availableChaptersDetail": {
                "sub": ["1", "2", "3", "4.5", "5", "6.5"],
                "raw": [],
            },
        }
    }
}

mock_processed_chapters: list[Chapter] = [
    Chapter(
        id="PBouNk6dWWBuswfX7:1",
        title="untitled",
        chapter_num=1.0,
        source=ContentSource.ALLMANGA,
    ),
    Chapter(
        id="PBouNk6dWWBuswfX7:2",
        title="untitled",
        chapter_num=2.0,
        source=ContentSource.ALLMANGA,
    ),
    Chapter(
        id="PBouNk6dWWBuswfX7:3",
        title="untitled",
        chapter_num=3.0,
        source=ContentSource.ALLMANGA,
    ),
    Chapter(
        id="PBouNk6dWWBuswfX7:4.5",
        title="untitled",
        chapter_num=4.5,
        source=ContentSource.ALLMANGA,
    ),
    Chapter(
        id="PBouNk6dWWBuswfX7:5",
        title="untitled",
        chapter_num=5.0,
        source=ContentSource.ALLMANGA,
    ),
    Chapter(
        id="PBouNk6dWWBuswfX7:6.5",
        title="untitled",
        chapter_num=6.5,
        source=ContentSource.ALLMANGA,
    ),
]

mock_manga_details_empty_chapters: dict = {
    "data": {"manga": {"_id": "empty123", "availableChaptersDetail": {"sub": [], "raw": []}}}
}

mock_manga_details_unsorted_chapters: dict = {
    "data": {
        "manga": {
            "_id": "test",
            "availableChaptersDetail": {
                "sub": ["10", "2", "1", "2.5"],
                "raw": [],
            },
        }
    }
}

mock_manga_details_empty_strings: dict = {
    "data": {
        "manga": {
            "_id": "test",
            "availableChaptersDetail": {"sub": ["1", "", "2"], "raw": []},
        }
    }
}

# Download resource data (from example_chapter_response.json partial)
mock_chapter_pages_response: dict = {
    "data": {
        "chapterPages": {
            "edges": [
                {
                    "pictureUrls": [
                        {"num": 0, "url": "images/test/chapter/sub_123/1.png"},
                        {"num": 1, "url": "images/test/chapter/sub_123/2.png"},
                    ],
                    "pictureUrlHead": "https://aln.youtube-anime.com/",
                }
            ]
        }
    }
}

mock_processed_download_resource: DownloadResource = DownloadResource(
    urls=[
        "https://ytimgf.youtube-anime.com/images/test/chapter/sub_123/1.png",
        "https://ytimgf.youtube-anime.com/images/test/chapter/sub_123/2.png",
    ],
    source=ContentSource.ALLMANGA,
)

mock_chapter_response_empty_pages: dict = {
    "data": {"chapterPages": {"edges": [{"pictureUrls": [], "pictureUrlHead": ""}]}}
}

mock_chapter_response_no_edges: dict = {"data": {"chapterPages": {"edges": []}}}

mock_chapter_pages_missing_urls: dict = {
    "data": {
        "chapterPages": {
            "edges": [
                {
                    "pictureUrls": [
                        {"url": "valid.jpg"},
                        {"url": ""},
                        {"url": None},
                    ],
                }
            ]
        }
    }
}
