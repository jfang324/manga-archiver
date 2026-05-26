from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.workers.jobs import UploadJob
from src.manga_archiver.workers.upload_worker import UploadWorker


def _with_invalid_fields(job: UploadJob, invalid_fields: dict[str, object]) -> UploadJob:
    for key, value in invalid_fields.items():
        object.__setattr__(job, key, value)

    return job


class TestUploadWorkerDoWork:
    def _create_mock_archive_store(self, uploaded_id: str | None = "file_123") -> MagicMock:
        archive_store = MagicMock()
        archive_store.upload_chapter = AsyncMock(return_value=uploaded_id)
        return archive_store

    def _create_job(self) -> UploadJob:
        return UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=AppConfig(_output_format=OutputFormat.PDF),
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
            source=ContentSource.MANGADEX,
        )

    def _create_worker(
        self, archive_store: MagicMock, notification_queue: AsyncMock | None = None
    ) -> UploadWorker:
        return UploadWorker(
            google_drive_archive_store=archive_store,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=notification_queue or AsyncMock(),
            config=MagicMock(),
        )

    @pytest.mark.asyncio
    async def test_do_work_uploads_file_successfully(self) -> None:
        mock_archive_store = self._create_mock_archive_store()
        worker = self._create_worker(mock_archive_store)

        job = self._create_job()
        result = await worker._do_work(job)

        mock_archive_store.upload_chapter.assert_called_once()
        call_kwargs = mock_archive_store.upload_chapter.call_args.kwargs
        assert call_kwargs["file_data"] == b"fake pdf data"
        assert call_kwargs["file_name"] == "Test Manga [1] - Chapter 1.pdf"
        assert call_kwargs["manga_title"] == "Test Manga"
        assert call_kwargs["source"] == "mangadex"
        assert call_kwargs["chapter_num"] == "1"
        assert call_kwargs["chapter_title"] == "Chapter 1"
        assert call_kwargs["mimetype"] == OutputFormat.PDF.mime_type
        assert result is None

    @pytest.mark.asyncio
    async def test_do_work_raises_when_upload_returns_none(self) -> None:
        mock_archive_store = self._create_mock_archive_store(uploaded_id=None)
        worker = self._create_worker(mock_archive_store)

        with pytest.raises(RuntimeError, match="Failed to upload"):
            await worker._do_work(self._create_job())

    @pytest.mark.asyncio
    async def test_do_work_raises_exception(self) -> None:
        mock_archive_store = self._create_mock_archive_store()
        mock_archive_store.upload_chapter = AsyncMock(side_effect=Exception("API error"))
        worker = self._create_worker(mock_archive_store)

        with pytest.raises(Exception, match="API error"):
            await worker._do_work(self._create_job())

    @pytest.mark.parametrize(
        "invalid_fields, expected_error_message",
        [
            ({"complete_file_data": None}, "complete_file_data"),
            ({"chapter_number": "not a number"}, "must be a float"),
            (
                {"full_name": "Test Manga [1] - Chapter 1.pdf", "chapter_number": 2.0},
                "full_name",
            ),
        ],
        ids=[
            "missing_complete_file_data",
            "invalid_chapter_number",
            "invalid_full_name",
        ],
    )
    @pytest.mark.asyncio
    async def test_do_work_raises_value_error_for_invalid_job(
        self, invalid_fields, expected_error_message
    ) -> None:
        mock_archive_store = MagicMock()
        mock_archive_store.upload_chapter = AsyncMock(return_value="file_id")

        job = self._create_job()

        job = _with_invalid_fields(job, invalid_fields)

        worker = self._create_worker(mock_archive_store)

        with pytest.raises(ValueError, match=expected_error_message):
            await worker._do_work(job)
        mock_archive_store.upload_chapter.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_wrong_job_type(self, mock_job) -> None:
        mock_archive_store = self._create_mock_archive_store()

        worker = self._create_worker(mock_archive_store)

        with pytest.raises(ValueError, match="Invalid job type"):
            await worker._do_work(mock_job)
        mock_archive_store.upload_chapter.assert_not_awaited()
