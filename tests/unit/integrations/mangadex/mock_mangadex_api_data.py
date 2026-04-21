"""Mock data for unit tests."""

from src.manga_archiver.models import Chapter, ContentSource, DownloadResource, Manga

# Manga search response data
mock_manga_data: dict = {
    "data": [
        {
            "id": "1",
            "attributes": {
                "title": {"en": "Attack on Titan"},
            },
            "status": "current",
        },
        {
            "id": "2",
            "attributes": {
                "title": {"en": "One Piece"},
            },
            "status": "current",
        },
        {
            "id": "3",
            "attributes": {
                "title": {"en": "Naruto"},
            },
            "status": "current",
        },
        {
            "id": "4",
            "attributes": {"title": {"sp": "Uno Piece"}},
            "status": "current",
        },
        {
            "attributes": {
                "title": {"en": "Naruto"},
                "status": "finished",
            },
        },
    ]
}

mock_processed_manga_data: list[Manga] = [
    Manga(id="1", title="Attack on Titan", source=ContentSource.MANGADEX),
    Manga(id="2", title="One Piece", source=ContentSource.MANGADEX),
    Manga(id="3", title="Naruto", source=ContentSource.MANGADEX),
    Manga(id="4", title="Uno Piece", source=ContentSource.MANGADEX),
]

# Chapter data response
mock_chapter_data: dict = {
    "data": [
        {
            "id": "1",
            "attributes": {
                "title": "Chapter 1",
                "chapter": "1",
            },
            "uploadDate": "2022-01-01T00:00:00.000Z",
        },
        {
            "id": "6",
            "attributes": {
                "title": "Chapter 1",
                "chapter": "1",
            },
            "uploadDate": "2022-01-01T00:00:00.000Z",
        },
        {
            "id": "2",
            "attributes": {
                "title": "Chapter 2",
                "chapter": "2",
            },
            "uploadDate": "2022-01-02T00:00:00.000Z",
        },
        {
            "id": "3",
            "attributes": {
                "chapter": "3",
            },
            "uploadDate": "2022-01-03T00:00:00.000Z",
        },
        {
            "id": "4",
            "attributes": {
                "title": "Chapter 4",
            },
            "uploadDate": "2022-01-04T00:00:00.000Z",
        },
        {
            "id": "5",
            "attributes": {
                "title": None,
                "chapter": "5",
            },
            "uploadDate": "2022-01-05T00:00:00.000Z",
        },
        {
            "id": "6",
            "attributes": {
                "title": "",
                "chapter": "6",
            },
            "uploadDate": "2022-01-06T00:00:00.000Z",
        },
        {
            "attributes": {
                "title": "Chapter 7",
                "chapter": "7",
            },
        },
    ]
}

mock_processed_chapter_data: list[Chapter] = [
    Chapter(id="1", title="Chapter 1", chapter_num=1.0, source=ContentSource.MANGADEX),
    Chapter(id="2", title="Chapter 2", chapter_num=2.0, source=ContentSource.MANGADEX),
    Chapter(id="3", title="untitled", chapter_num=3.0, source=ContentSource.MANGADEX),
    Chapter(id="5", title="untitled", chapter_num=5.0, source=ContentSource.MANGADEX),
    Chapter(id="6", title="untitled", chapter_num=6.0, source=ContentSource.MANGADEX),
]

# # Download resource response
mock_malformed_download_resource_data: dict = {
    "baseUrl": "https://mangaCDN.com",
    "chapter": {
        "hash": "hash",
        "data": [
            "chapter1.png",
            "chapter2.png",
        ],
    },
}

# Download resource with data-saver
mock_download_resource_data: dict = {
    "baseUrl": "https://mangaCDN.com",
    "chapter": {
        "hash": "hash",
        "data": [
            "chapter1.png",
            "chapter2.png",
        ],
        "dataSaver": [
            "chapter1-saver.jpg",
            "chapter2-saver.jpg",
        ],
    },
}

# processed resource with no data-saver
mock_processed_download_resource_data: DownloadResource = DownloadResource(
    urls=[
        "https://mangaCDN.com/data/hash/chapter1.png",
        "https://mangaCDN.com/data/hash/chapter2.png",
    ],
    source=ContentSource.MANGADEX,
)

# processed resource with data-saver
mock_processed_download_resource_data_saver: DownloadResource = DownloadResource(
    urls=[
        "https://mangaCDN.com/data-saver/hash/chapter1-saver.jpg",
        "https://mangaCDN.com/data-saver/hash/chapter2-saver.jpg",
    ],
    source=ContentSource.MANGADEX,
)

# Nested test data for _get_nested helper
mock_nested_data: dict = {
    "title": {"en": "Test Title"},
    "altTitles": [{"ja": "Japanese Title"}, {"ko": "Korean Title"}],
    "description": {"en": "Description here"},
    "empty": {},
    "null_value": None,
}

# Empty response data
mock_empty_manga_data: dict = {"data": []}
mock_empty_chapter_data: dict = {"data": []}
