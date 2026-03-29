"""Unit tests for MergeWorker."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.mangadex_downloader.models.app_config import OutputFormat
from src.mangadex_downloader.workers.jobs import BenchmarkJob, JobStatus, MergingJob
from src.mangadex_downloader.workers.merge_worker import MergeWorker


class TestMergeWorkerDoWork:
    """Test MergeWorker._do_work method."""

    @pytest.mark.asyncio
    async def test_do_work_returns_benchmark_job(self):
        """Test that _do_work returns a BenchmarkJob with correct fields."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

        mock_on_status_change = MagicMock()

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        assert isinstance(result, BenchmarkJob)
        assert result.id == "job_123"
        assert result.manga_title == "Test Manga"
        assert result.output_directory == Path("/output")
        assert result.output_format == OutputFormat.PDF

    @pytest.mark.asyncio
    async def test_do_work_calls_pdf_generator(self):
        """Test that pdf_generator.generate is called with correct arguments."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_pdf_generator.generate.assert_called_once_with(
            image_data_list=[b"image1", b"image2"],
            output_directory=Path("/output"),
            output_name="Test Manga [1] - Introduction",
            output_format=OutputFormat.PDF,
        )

    @pytest.mark.asyncio
    async def test_do_work_calls_status_change_merging(self):
        """Test that on_status_change is called with MERGING."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

        mock_on_status_change = MagicMock()

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=mock_on_status_change,
            config=MagicMock(),
        )

        await worker._do_work(job)

        mock_on_status_change.assert_called_once_with("job_123", JobStatus.MERGING)

    @pytest.mark.asyncio
    async def test_do_work_parses_chapter_title_with_number(self):
        """Test that chapter title is parsed correctly: '1. Introduction' -> '[1] - Introduction'."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        # Verify the output name format: "Manga Title [chapter_num] - title"
        mock_pdf_generator.generate.assert_called_once()
        call_kwargs = mock_pdf_generator.generate.call_args.kwargs
        assert call_kwargs["output_name"] == "One Piece [100] - The Final Battle"

    @pytest.mark.asyncio
    async def test_do_work_parses_chapter_title_strips_trailing_dot(self):
        """Test that trailing dot is stripped from chapter number: '1.' -> '1'."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        await worker._do_work(job)

        call_kwargs = mock_pdf_generator.generate.call_args.kwargs
        assert call_kwargs["output_name"] == "Test Manga [5] - Start"

    @pytest.mark.asyncio
    async def test_do_work_sets_end_time_after_generation(self):
        """Test that end_time is set after PDF generation."""
        mock_pdf_generator = MagicMock()
        mock_pdf_generator.generate.return_value = "/output/path/test.pdf"

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
            pdf_generator=mock_pdf_generator,
            worker_id="merge_worker_0",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=MagicMock(),
        )

        result = await worker._do_work(job)

        # end_time should be set to a positive value (after start_time=1000)
        assert result.end_time > 0
        assert result.end_time >= result.start_time
