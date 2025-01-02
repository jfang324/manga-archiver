from src.mangadex_downloader.services.data_processing_service import *
from tests.mock_data import *


class TestProcessMangaData:
    def test_process_manga_data_returns_correct_data(self):
        response: list[dict] = process_manga_data(mock_manga_data)

        assert response == mock_processed_manga_data

    def test_process_manga_data_returns_correct_data_with_no_title(self):
        response: list[dict] = process_manga_data(
            {
                "data": [
                    {
                        "id": "4",
                        "attributes": {
                            "title": {
                                "br": "Naruto",
                            },
                        },
                        "status": "current",
                    }
                ]
            }
        )

        assert response == [
            {
                "title": "Naruto",
                "id": "4",
            }
        ]

    def test_process_manga_data_returns_correct_data_with_no_id(self):
        response: list[dict] = process_manga_data(
            {
                "data": [
                    {
                        "attributes": {
                            "title": {"en": "Naruto"},
                            "status": "finished",
                        },
                    }
                ]
            }
        )

        assert response == []


class TestProcessChapterData:
    def test_process_chapter_data_returns_correct_data(self):
        response: list[dict] = process_chapter_data(mock_chapter_data)

        assert response == mock_processed_chapter_data

    def test_process_chapter_data_returns_correct_data_with_no_title(self):
        response: list[dict] = process_chapter_data(
            {
                "data": [
                    {
                        "id": "4",
                        "attributes": {"chapter": "4"},
                        "uploadDate": "2022-01-04T00:00:00.000Z",
                    }
                ]
            }
        )

        assert response == [
            {
                "title": None,
                "id": "4",
                "chapter_number": "4",
            }
        ]

    def test_process_chapter_data_returns_correct_data_with_no_id(self):
        response: list[dict] = process_chapter_data(
            {
                "data": [
                    {
                        "attributes": {
                            "title": "Chapter 5",
                            "chapter": "5",
                        },
                    }
                ]
            }
        )

        assert response == []

    def test_process_chapter_data_returns_correct_data_with_no_chapter_number(self):
        response: list[dict] = process_chapter_data(
            {
                "data": [
                    {
                        "id": "5",
                        "attributes": {
                            "title": "Chapter 5",
                        },
                    }
                ]
            }
        )

        assert response == [{"title": "Chapter 5", "id": "5", "chapter_number": "0"}]


class TestProcessDownloadResourceData:
    def test_process_download_resource_data_returns_correct_data(self):
        response: list[str] = process_download_resource_data(
            mock_download_resource_data
        )

        assert response == mock_processed_download_resource_data
