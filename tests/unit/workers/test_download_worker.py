from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.utils.downloader import DownloadClient
from src.manga_archiver.workers.download_worker import DownloadWorker
from src.manga_archiver.workers.jobs import DownloadingJob, MergingJob


class TestDownloadWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_returns_merging_job(self, mock_semaphore):
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1", b"image2"])

        mock_notification_queue = AsyncMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert isinstance(result, MergingJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.chapter_title == "Chapter 1"
        assert result.image_data == [b"image1", b"image2"]

    @pytest.mark.asyncio
    async def test_do_work_calls_download_client_with_urls(self, mock_semaphore):
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_download_client.download_images.assert_called_once_with(
            ["http://example.com/1.jpg", "http://example.com/2.jpg"]
        )

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_downloading(self, mock_semaphore):
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        mock_notification_queue = AsyncMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg"],
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        assert mock_notification_queue.put.call_count == 2

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_urls(self):
        mock_download_client = MagicMock(spec=DownloadClient)

        mock_semaphore = MagicMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=[],
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match="Invalid DownloadingJob missing urls"):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_uses_semaphore(self, mock_semaphore):
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number="1",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg"],
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_semaphore.__aenter__.assert_called()
        mock_semaphore.__aexit__.assert_called()
