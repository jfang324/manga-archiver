from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.workers.jobs import (
    DownloadingJob,
    FetchingResourcesJob,
)
from src.mangadex_downloader.workers.resolve_worker import ResolveWorker


class TestResolveWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_returns_downloading_job(self):
        mock_api_client = AsyncMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={
                "urls": ["http://example.com/1.jpg", "http://example.com/2.jpg"]
            }
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_notification_queue = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            id="resolve_worker_0",
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
    async def test_do_work_calls_api_client_with_chapter_id(self):
        mock_api_client = AsyncMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={"urls": ["http://example.com/1.jpg"]}
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_api_client.get_download_resource.assert_called_once_with("chapter_456")

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change(self):
        mock_api_client = AsyncMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={"urls": ["http://example.com/1.jpg"]}
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_notification_queue = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_notification_queue.put.assert_called_once()

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_chapter_id(self):
        mock_api_client = AsyncMock()

        mock_semaphore = MagicMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        with pytest.raises(
            ValueError, match="Invalid FetchingResourcesJob missing chapter_id"
        ):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_uses_semaphore(self):
        mock_api_client = AsyncMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={"urls": ["http://example.com/1.jpg"]}
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        # Verify semaphore was entered and exited
        mock_semaphore.__aenter__.assert_called()
        mock_semaphore.__aexit__.assert_called()
