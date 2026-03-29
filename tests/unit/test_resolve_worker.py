"""Unit tests for ResolveWorker."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.workers.jobs import (
    DownloadingJob,
    FetchingResourcesJob,
    JobStatus,
)
from src.mangadex_downloader.workers.resolve_worker import ResolveWorker


class TestResolveWorkerDoWork:
    """Test ResolveWorker._do_work method."""

    @pytest.mark.asyncio
    async def test_do_work_returns_downloading_job(self):
        """Test that _do_work returns a DownloadingJob with correct fields."""
        mock_api_client = MagicMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={
                "urls": ["http://example.com/1.jpg", "http://example.com/2.jpg"]
            }
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_on_status_change = MagicMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=-1,
            end_time=-1,
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
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
        """Test that API client is called with correct chapter_id."""
        mock_api_client = MagicMock()
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
            start_time=-1,
            end_time=-1,
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_api_client.get_download_resource.assert_called_once_with("chapter_456")

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change(self):
        """Test that on_status_change is called with FETCHING_RESOURCES."""
        mock_api_client = MagicMock()
        mock_api_client.get_download_resource = AsyncMock(
            return_value={"urls": ["http://example.com/1.jpg"]}
        )

        mock_semaphore = MagicMock()
        mock_semaphore.__aenter__ = AsyncMock()
        mock_semaphore.__aexit__ = AsyncMock()

        mock_on_status_change = MagicMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=-1,
            end_time=-1,
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_on_status_change.assert_called_once_with(
            "job_123", JobStatus.FETCHING_RESOURCES
        )

    @pytest.mark.asyncio
    async def test_do_work_raises_error_for_missing_chapter_id(self):
        """Test that ValueError is raised when chapter_id is missing."""
        mock_api_client = MagicMock()

        mock_semaphore = MagicMock()

        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            chapter_id="",  # Empty chapter_id
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=-1,
            end_time=-1,
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        with pytest.raises(
            ValueError, match="Invalid FetchingResourcesJob missing chapter_id"
        ):
            await worker._do_work(job)

    @pytest.mark.asyncio
    async def test_do_work_uses_semaphore(self):
        """Test that semaphore is acquired before API call."""
        mock_api_client = MagicMock()
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
            start_time=-1,
            end_time=-1,
        )

        worker = ResolveWorker(
            api_client=mock_api_client,
            semaphore=mock_semaphore,
            worker_id="resolve_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        # Verify semaphore was entered and exited
        mock_semaphore.__aenter__.assert_called()
        mock_semaphore.__aexit__.assert_called()
