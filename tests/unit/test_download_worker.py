"""Unit tests for DownloadWorker."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.workers.download_worker import DownloadWorker
from src.mangadex_downloader.workers.jobs import DownloadingJob, JobStatus, MergingJob


class TestDownloadWorkerDoWork:
    """Test DownloadWorker._do_work method."""

    @pytest.mark.asyncio
    async def test_do_work_returns_merging_job(self):
        """Test that _do_work returns a MergingJob with correct fields."""
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(
            return_value=[b"image1", b"image2"]
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_on_status_change = MagicMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
            start_time=1000,
            end_time=-1,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert isinstance(result, MergingJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.chapter_title == "Chapter 1"
        assert result.image_data == [b"image1", b"image2"]

    @pytest.mark.asyncio
    async def test_do_work_calls_download_client_with_urls(self):
        """Test that download client is called with correct URLs."""
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
            start_time=1000,
            end_time=-1,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_download_client.download_images.assert_called_once_with(
            ["http://example.com/1.jpg", "http://example.com/2.jpg"]
        )

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_downloading(self):
        """Test that on_status_change is called with DOWNLOADING."""
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_on_status_change = MagicMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg"],
            start_time=1000,
            end_time=-1,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_on_status_change.assert_called_once_with("job_123", JobStatus.DOWNLOADING)

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_urls(self):
        """Test that ValueError is raised when urls is empty."""
        mock_download_client = MagicMock()

        mock_semaphore = MagicMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=[],  # Empty URLs
            start_time=1000,
            end_time=-1,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match="Invalid DownloadingJob missing urls"):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_uses_semaphore(self):
        """Test that semaphore is acquired before download."""
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            urls=["http://example.com/1.jpg"],
            start_time=1000,
            end_time=-1,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            semaphore=mock_semaphore,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_semaphore.__aenter__.assert_called()
        mock_semaphore.__aexit__.assert_called()
