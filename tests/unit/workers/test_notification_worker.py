from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mangadex_downloader.enums import JobStatus, OutputFormat
from src.mangadex_downloader.workers.jobs import JobMetadata, NotificationJob
from src.mangadex_downloader.workers.notification_worker import NotificationWorker


class TestNotificationWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_calls_callback_with_job_data(self):
        mock_callback = MagicMock()
        worker = NotificationWorker(
            id="test_notification_worker",
            input_queue=MagicMock(),
            on_status_update=mock_callback,
        )

        job = NotificationJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            start_time=1000,
            end_time=2000,
            status=JobStatus.COMPLETED,
        )

        await worker._do_work(job)

        mock_callback.assert_called_once()
        call_args = mock_callback.call_args[0]
        assert call_args[0] == "job_123"
        assert call_args[1] == JobStatus.COMPLETED
        assert isinstance(call_args[2], JobMetadata)
        assert call_args[2].manga_title == "Test Manga"
        assert call_args[2].chapter_title == "Chapter 1"

    @pytest.mark.asyncio
    async def test_do_work_extracts_metadata_from_job(self):
        mock_callback = MagicMock()
        worker = NotificationWorker(
            id="test_notification_worker",
            input_queue=MagicMock(),
            on_status_update=mock_callback,
        )

        job = NotificationJob(
            id="job_456",
            manga_title="One Piece",
            chapter_title="Chapter 100",
            output_directory=Path("/downloads"),
            output_format=OutputFormat.CBZ,
            start_time=5000,
            end_time=8000,
            status=JobStatus.DOWNLOADING,
        )

        await worker._do_work(job)

        mock_callback.assert_called_once()
        job_id, status, metadata = mock_callback.call_args[0]

        assert job_id == "job_456"
        assert status == JobStatus.DOWNLOADING
        assert metadata.chapter_id == "job_456"
        assert metadata.manga_title == "One Piece"
        assert metadata.chapter_title == "Chapter 100"
        assert metadata.start_time == 5000
        assert metadata.end_time == 8000


class TestNotificationWorker:
    def test_stop_sets_running_false(self):
        worker = NotificationWorker(
            id="test_notification_worker",
            input_queue=MagicMock(),
            on_status_update=MagicMock(),
        )

        worker.stop()

        assert worker._running is False
