from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.utils.download_limiter import DownloadLimiter
from src.manga_archiver.utils.downloader import DownloadClient
from src.manga_archiver.workers.download_worker import DownloadWorker
from src.manga_archiver.workers.jobs import DownloadingJob, MergingJob


class TestDownloadWorkerDoWork:
    def _create_mock_provider_manager(self, limiter: DownloadLimiter) -> MagicMock:
        manager = MagicMock()
        manager.get_download_limiter = MagicMock(return_value=limiter)
        manager.invalidate_cache = AsyncMock()
        return manager

    @pytest.mark.asyncio
    async def test_do_work_returns_merging_job(self) -> None:
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1", b"image2"])
        test_limiter = DownloadLimiter(5)
        mock_notification_queue = AsyncMock()
        app_config = AppConfig(optimize=True)

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=app_config,
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
            chapter_id="test_manga:1",
            source=ContentSource.MANGADEX,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=self._create_mock_provider_manager(test_limiter),
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
        assert result.app_config is app_config
        assert result.image_data == [b"image1", b"image2"]

    @pytest.mark.asyncio
    async def test_do_work_calls_download_client_with_urls(self) -> None:
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])
        test_limiter = DownloadLimiter(5)
        app_config = AppConfig(optimize=True)

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=app_config,
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
            chapter_id="test_manga:1",
            source=ContentSource.MANGADEX,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=self._create_mock_provider_manager(test_limiter),
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        mock_download_client.download_images.assert_called_once_with(
            ["http://example.com/1.jpg", "http://example.com/2.jpg"], test_limiter, {}
        )
        assert result.app_config is app_config

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_downloading(self) -> None:
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(return_value=[b"image1"])
        test_limiter = DownloadLimiter(5)
        mock_notification_queue = AsyncMock()
        app_config = AppConfig(optimize=True)

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=app_config,
            urls=["http://example.com/1.jpg", "http://example.com/2.jpg"],
            chapter_id="test_manga:1",
            source=ContentSource.MANGADEX,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=self._create_mock_provider_manager(test_limiter),
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        assert mock_notification_queue.put.call_count == 2

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_urls(self) -> None:
        mock_download_client = MagicMock(spec=DownloadClient)
        test_limiter = DownloadLimiter(5)

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=AppConfig(),
            urls=[],
            chapter_id="test_manga:1",
            source=ContentSource.MANGADEX,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=self._create_mock_provider_manager(test_limiter),
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match="Invalid DownloadingJob missing urls"):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_wrong_job_type(self, mock_job) -> None:
        mock_download_client = MagicMock(spec=DownloadClient)
        test_limiter = DownloadLimiter(5)

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=self._create_mock_provider_manager(test_limiter),
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match="Invalid job type"):
            await worker._do_work(mock_job)

    @pytest.mark.asyncio
    async def test_do_work_preserves_download_error_when_cache_invalidation_fails(self) -> None:
        download_error = RuntimeError("download failed")
        mock_download_client = MagicMock()
        mock_download_client.download_images = AsyncMock(side_effect=download_error)
        test_limiter = DownloadLimiter(5)
        mock_provider_manager = self._create_mock_provider_manager(test_limiter)
        mock_provider_manager.invalidate_cache = AsyncMock(
            side_effect=RuntimeError("cache delete failed")
        )

        job = DownloadingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            app_config=AppConfig(),
            urls=["http://example.com/1.jpg"],
            chapter_id="test_manga:1",
            source=ContentSource.MANGADEX,
        )

        worker = DownloadWorker(
            download_client=mock_download_client,
            provider_manager=mock_provider_manager,
            worker_id="download_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(RuntimeError, match="download failed"):
            await worker._do_work(job)
