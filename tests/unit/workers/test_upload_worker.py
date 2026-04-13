from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.enums import JobStatus, OutputFormat
from src.manga_archiver.workers.jobs import UploadJob
from src.manga_archiver.workers.upload_worker import UploadWorker


class TestUploadWorkerDoWork:
    def _create_mock_drive_client(self, uploaded_id: str | None = "folder_123"):
        client = MagicMock()
        client.get_or_create_manga_folder = AsyncMock(return_value="folder_123")
        client.upload_file = AsyncMock(return_value=uploaded_id)
        return client

    @pytest.mark.asyncio
    async def test_do_work_uploads_file_successfully(self):
        mock_drive_client = self._create_mock_drive_client()
        mock_notification_queue = AsyncMock()

        job = UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=OutputFormat.PDF,
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
        )

        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        mock_drive_client.get_or_create_manga_folder.assert_called_once_with("Test Manga")
        mock_drive_client.upload_file.assert_called_once_with(
            file_data=b"fake pdf data",
            file_name="Test Manga [1] - Chapter 1.pdf",
            folder_id="folder_123",
            mimetype=OutputFormat.PDF.mime_type,
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_do_work_sends_completed_notification(self):
        mock_drive_client = self._create_mock_drive_client()
        mock_notification_queue = AsyncMock()

        job = UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=OutputFormat.PDF,
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
        )

        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        assert mock_notification_queue.put.call_count == 2
        notifications = mock_notification_queue.put.call_args_list
        assert notifications[0][0][0].status == JobStatus.UPLOADING
        assert notifications[1][0][0].status == JobStatus.UPLOADING

    @pytest.mark.asyncio
    async def test_do_work_sends_failed_notification_when_upload_returns_none(self):
        mock_drive_client = self._create_mock_drive_client(uploaded_id=None)
        mock_notification_queue = AsyncMock()

        job = UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=OutputFormat.PDF,
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
        )

        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert result is None
        assert mock_notification_queue.put.call_count == 2
        notifications = mock_notification_queue.put.call_args_list
        assert notifications[0][0][0].status == JobStatus.UPLOADING
        assert notifications[1][0][0].status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_do_work_raises_exception(self):
        mock_drive_client = self._create_mock_drive_client()
        mock_drive_client.get_or_create_manga_folder = AsyncMock(side_effect=Exception("API error"))

        job = UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=OutputFormat.PDF,
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
        )

        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(Exception, match="API error"):
            await worker._do_work(job)

    @pytest.mark.parametrize(
        "invalid_fields, expected_error_message",
        [
            ({"complete_file_data": None}, "complete_file_data"),
            ({"chapter_number": "not a number"}, "must be a float"),
            ({"full_name": "Test Manga [1] - Chapter 1.pdf", "chapter_number": 2.0}, "full_name"),
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
    ):
        mock_drive_client = MagicMock()
        mock_drive_client.get_or_create_manga_folder.return_value = "folder_id"

        job = UploadJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=OutputFormat.PDF,
            complete_file_data=b"fake pdf data",
            full_name="Test Manga [1] - Chapter 1.pdf",
        )

        for key, value in invalid_fields.items():
            setattr(job, key, value)

        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match=expected_error_message):
            await worker._do_work(job)


class TestUploadWorker:
    def test_stop_sets_running_false(self):
        mock_drive_client = MagicMock()
        worker = UploadWorker(
            google_drive_client=mock_drive_client,
            worker_id="upload_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=MagicMock(),
            config=MagicMock(),
        )

        worker.stop()

        assert worker._running is False
