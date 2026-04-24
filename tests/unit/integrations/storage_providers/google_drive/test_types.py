import pytest

from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    MAX_APP_PROPERTY_BYTES,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
    _truncate_for_app_properties,
)


class TestTruncateForAppProperties:
    @pytest.mark.parametrize(
        ("key", "value"),
        [
            ("source", "mangadex"),
            ("chapter_title", "x" * 200),
            ("chapter_title", "日本語" * 50),
            ("source", "x" * 120),
            ("x" * 30, "value"),
        ],
    )
    def test_truncates_to_limit(self, key: str, value: str) -> None:
        result = _truncate_for_app_properties(key, value)
        total_bytes = len(key.encode("utf-8")) + len(result.encode("utf-8"))
        assert total_bytes <= MAX_APP_PROPERTY_BYTES


class TestGoogleDriveFolderMetadata:
    @pytest.mark.parametrize(
        ("source",),
        [
            ("mangadex",),
            ("x" * 200,),
        ],
    )
    def test_to_app_properties_truncates_long_source(self, source: str) -> None:
        metadata = GoogleDriveFolderMetadata(source=source)
        props = metadata.to_app_properties()
        total_bytes = len(b"source") + len(props["source"].encode("utf-8"))
        assert total_bytes <= MAX_APP_PROPERTY_BYTES

    def test_roundtrip(self) -> None:
        original = GoogleDriveFolderMetadata(source="mangadex")
        props = original.to_app_properties()
        restored = GoogleDriveFolderMetadata.from_app_properties(props)
        assert restored.source == original.source


class TestGoogleDriveFileMetadata:
    @pytest.mark.parametrize(
        ("chapter_title",),
        [
            ("Test Chapter",),
            ("x" * 200,),
        ],
    )
    def test_to_app_properties_truncates_long_title(self, chapter_title: str) -> None:
        metadata = GoogleDriveFileMetadata(
            source="mangadex",
            chapter_num="1",
            chapter_title=chapter_title,
        )
        props = metadata.to_app_properties()
        total_bytes = len(b"chapter_title") + len(props["chapter_title"].encode("utf-8"))
        assert total_bytes <= MAX_APP_PROPERTY_BYTES

    def test_roundtrip(self) -> None:
        original = GoogleDriveFileMetadata(
            source="mangadex",
            chapter_num="1",
            chapter_title="Test Chapter",
        )
        props = original.to_app_properties()
        restored = GoogleDriveFileMetadata.from_app_properties(props)
        assert restored.source == original.source
        assert restored.chapter_num == original.chapter_num
        assert restored.chapter_title == original.chapter_title
