from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.enums import JobStatus, OutputFormat
from src.mangadex_downloader.workers.jobs import BenchmarkJob, MergingJob
from src.mangadex_downloader.workers.merge_worker import MergeWorker


class TestMergeWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_returns_benchmark_job(self):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        mock_notification_queue = AsyncMock()

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="1. Introduction",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1", b"image2"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert isinstance(result, BenchmarkJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.output_directory == Path("/output")
        assert result.output_format == OutputFormat.PDF

    @pytest.mark.asyncio
    async def test_do_work_calls_multi_format_exporter(self):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="1. Introduction",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1", b"image2"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_multi_format_exporter.generate.assert_called_once_with(
            image_data_list=[b"image1", b"image2"],
            output_directory=Path("/output"),
            output_name="Test Manga [1] - Introduction",
            output_format=OutputFormat.PDF,
        )

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_merging(self):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        mock_notification_queue = AsyncMock()

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="1. Introduction",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=mock_notification_queue,
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.MERGING

    @pytest.mark.asyncio
    async def test_do_work_parses_chapter_title_with_number(self):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        job = MergingJob(
            id="job_123",
            manga_title="One Piece",
            chapter_title="100. The Final Battle",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        # Verify the output name format: "Manga Title [chapter_num] - title"
        mock_multi_format_exporter.generate.assert_called_once()
        call_kwargs = mock_multi_format_exporter.generate.call_args.kwargs
        assert call_kwargs["output_name"] == "One Piece [100] - The Final Battle"

    @pytest.mark.asyncio
    async def test_do_work_parses_chapter_title_strips_trailing_dot(self):
        """Test that trailing dot is stripped from chapter number: '1.' -> '1'."""
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="5. Start",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        call_kwargs = mock_multi_format_exporter.generate.call_args.kwargs
        assert call_kwargs["output_name"] == "Test Manga [5] - Start"

    @pytest.mark.asyncio
    async def test_do_work_sets_end_time_after_generation(self):
        mock_multi_format_exporter = MagicMock()
        mock_multi_format_exporter.generate.return_value = "/output/path/test.pdf"

        job = MergingJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="1. Introduction",
            output_directory=Path("/output"),
            output_format=OutputFormat.PDF,
            image_data=[b"image1"],
            start_time=1000,
            end_time=-1,
        )

        worker = MergeWorker(
            multi_format_exporter=mock_multi_format_exporter,
            id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            notification_queue=AsyncMock(),
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        # end_time should be set to a positive value (after start_time=1000)
        assert result.end_time > 0
        assert result.end_time >= result.start_time
