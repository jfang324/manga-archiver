from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.types import ContentSource, DownloadResource
from src.manga_archiver.workers.jobs import (
    DownloadingJob,
    FetchingResourcesJob,
)
from src.manga_archiver.workers.resolve_worker import ResolveWorker


class TestResolveWorkerDoWork:
    def _create_mock_provider_manager(self, urls: list[str] | None = None):
        manager = MagicMock()
        manager.get_download_resource = AsyncMock(
            return_value=DownloadResource(
                urls=urls or ["http://example.com/1.jpg"],
                source=ContentSource.MANGADEX,
            )
        )
        return manager

    @pytest.mark.asyncio
    async def test_do_work_returns_downloading_job(self, mock_semaphore):
        mock_provider_manager = self._create_mock_provider_manager(
            ["http://example.com/1.jpg", "http://example.com/2.jpg"]
        )

        mock_notification_queue = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            source=ContentSource.MANGADEX,
        )

        worker = ResolveWorker(
            provider_manager=mock_provider_manager,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert isinstance(result, DownloadingJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.chapter_title == "Chapter 1"
        assert result.urls == ["http://example.com/1.jpg", "http://example.com/2.jpg"]

    @pytest.mark.asyncio
    async def test_do_work_calls_provider_manager_with_source_and_chapter_id(self, mock_semaphore):
        mock_provider_manager = self._create_mock_provider_manager()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            source=ContentSource.MANGADEX,
        )

        worker = ResolveWorker(
            provider_manager=mock_provider_manager,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_provider_manager.get_download_resource.assert_called_once_with(
            ContentSource.MANGADEX, "chapter_456"
        )

    @pytest.mark.asyncio
    async def test_do_work_sends_notification(self, mock_semaphore):
        mock_provider_manager = self._create_mock_provider_manager()

        mock_notification_queue = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            source=ContentSource.MANGADEX,
        )

        worker = ResolveWorker(
            provider_manager=mock_provider_manager,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        assert mock_notification_queue.put.call_count == 2

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_chapter_id(self, mock_semaphore):
        mock_provider_manager = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            source=ContentSource.MANGADEX,
        )

        worker = ResolveWorker(
            provider_manager=mock_provider_manager,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(ValueError, match="Invalid FetchingResourcesJob missing chapter_id"):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_uses_semaphore(self, mock_semaphore):
        mock_provider_manager = self._create_mock_provider_manager()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            source=ContentSource.MANGADEX,
        )

        worker = ResolveWorker(
            provider_manager=mock_provider_manager,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_semaphore.__aenter__.assert_called()
        mock_semaphore.__aexit__.assert_called()
