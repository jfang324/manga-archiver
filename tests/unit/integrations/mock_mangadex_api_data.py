"""Mock data for unit tests."""

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

mock_processed_manga_data: list[dict] = [
    {
        "title": "Attack on Titan",
        "id": "1",
    },
    {
        "title": "One Piece",
        "id": "2",
    },
    {
        "title": "Naruto",
        "id": "3",
    },
    {
        "title": "Uno Piece",
        "id": "4",
    },
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
            "attributes": {
                "title": "Chapter 5",
                "chapter": "5",
            },
        },
    ]
}

mock_processed_chapter_data: list[dict] = [
    {
        "title": "Chapter 1",
        "id": "1",
        "chapter": "1",
    },
    {
        "title": "Chapter 2",
        "id": "2",
        "chapter": "2",
    },
    {
        "title": "untitled",
        "id": "3",
        "chapter": "3",
    },
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
mock_processed_download_resource_data: dict = {
    "urls": [
        "https://mangaCDN.com/data/hash/chapter1.png",
        "https://mangaCDN.com/data/hash/chapter2.png",
    ],
    "hash": "hash",
}

# processed resource with data-saver
mock_processed_download_resource_data_saver: dict = {
    "urls": [
        "https://mangaCDN.com/data-saver/hash/chapter1-saver.jpg",
        "https://mangaCDN.com/data-saver/hash/chapter2-saver.jpg",
    ],
    "hash": "hash",
}

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
