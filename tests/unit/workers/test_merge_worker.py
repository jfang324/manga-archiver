from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.enums import OutputFormat
from src.mangadex_downloader.workers.jobs import MergingJob, UploadJob
from src.mangadex_downloader.workers.merge_worker import MergeWorker


class TestMergeWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_returns_upload_job(self, tmp_path):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = ("test.pdf", [])

        mock_notification_queue = AsyncMock()

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Introduction",
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            image_data=[b"image1", b"image2"],
        )

        mock_config = MagicMock()

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=mock_config,
        )

        result = await worker._do_work(job)

        assert isinstance(result, UploadJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.output_directory == tmp_path
        assert result.output_format == OutputFormat.PDF
        assert result.full_name == "test.pdf"

    @pytest.mark.asyncio
    async def test_do_work_calls_multi_format_exporter(self, tmp_path):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = ("test.pdf", [])

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Introduction",
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            image_data=[b"image1", b"image2"],
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_multi_format_exporter.generate.assert_called_once_with(
            image_data_list=[b"image1", b"image2"],
            output_directory=tmp_path,
            output_name="Test Manga [1] - Introduction",
            output_format=OutputFormat.PDF,
            return_bytes=True,
        )

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_merging(self, tmp_path):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = ("test.pdf", [])

        mock_notification_queue = AsyncMock()

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Introduction",
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            image_data=[b"image1", b"image2"],
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        assert mock_notification_queue.put.call_count == 2

    @pytest.mark.asyncio
    async def test_do_work_uses_chapter_number_from_job(self, tmp_path):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = ("test.pdf", [])

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="5",
            chapter_title="Chapter 5",
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            image_data=[b"image1"],
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        result = await worker._do_work(job)
        assert result.chapter_title == "Chapter 5"
        assert result.chapter_number == "5"
