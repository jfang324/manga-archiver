"""Unit tests for BenchmarkWorker."""

from unittest.mock import MagicMock

import pytest

from src.mangadex_downloader.workers.base import WorkerConfig
from src.mangadex_downloader.workers.benchmark_worker import BenchmarkWorker
from src.mangadex_downloader.workers.jobs import BenchmarkJob


class TestBenchmarkWorkerDoWork:
    """Test BenchmarkWorker._do_work method."""

    @pytest.mark.asyncio
    async def test_do_work_tracks_valid_job_timing(self):
        """Test that valid job timing is recorded."""
        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
        )

        job = BenchmarkJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=1000,
            end_time=5000,
        )

        await worker._do_work(job)

        assert len(worker._job_timings) == 1
        assert worker._job_timings[0] == (1000, 5000)

    @pytest.mark.asyncio
    async def test_do_work_ignores_invalid_start_time(self):
        """Test that timing is NOT recorded when start_time is -1."""
        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
        )

        job = BenchmarkJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=-1,
            end_time=5000,
        )

        await worker._do_work(job)

        assert len(worker._job_timings) == 0

    @pytest.mark.asyncio
    async def test_do_work_ignores_invalid_end_time(self):
        """Test that timing is NOT recorded when end_time is -1."""
        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
        )

        job = BenchmarkJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=1000,
            end_time=-1,
        )

        await worker._do_work(job)

        assert len(worker._job_timings) == 0

    @pytest.mark.asyncio
    async def test_do_work_calls_report_when_expected_count_reached(self):
        """Test that _report_benchmark is called when expected count is reached."""
        mock_callback = MagicMock()

        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
            expected_count=2,
            benchmark_callback=mock_callback,
        )

        job = BenchmarkJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=1000,
            end_time=5000,
        )

        await worker._do_work(job)
        assert mock_callback.call_count == 0

        await worker._do_work(job)
        assert mock_callback.call_count == 1

    @pytest.mark.asyncio
    async def test_do_work_does_not_report_before_expected_count(self):
        """Test that callback is NOT called before expected count is reached."""
        mock_callback = MagicMock()

        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
            expected_count=3,
            benchmark_callback=mock_callback,
        )

        job = BenchmarkJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_title="Chapter 1",
            output_directory=MagicMock(),
            output_format=MagicMock(),
            start_time=1000,
            end_time=5000,
        )

        await worker._do_work(job)
        await worker._do_work(job)

        mock_callback.assert_not_called()

    def test_report_calculates_earliest_and_latest(self):
        """Test that _report_benchmark calculates earliest and latest correctly."""
        mock_callback = MagicMock()

        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
            expected_count=2,
            benchmark_callback=mock_callback,
        )

        worker._job_timings = [
            (1000, 5000),
            (2000, 8000),
            (1500, 3000),
        ]

        worker._report_benchmark()

        mock_callback.assert_called_once_with(1000, 8000)

    def test_report_calls_callback(self):
        """Test that benchmark_callback is invoked with correct timings."""
        mock_callback = MagicMock()

        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
            benchmark_callback=mock_callback,
        )

        worker._job_timings = [(1000, 5000)]

        worker._report_benchmark()

        mock_callback.assert_called_once()

    def test_report_does_not_crash_with_empty_timings(self):
        """Test that _report_benchmark handles empty timings list."""
        worker = BenchmarkWorker(
            worker_id="benchmark_worker_0",
            input_queue=MagicMock(),
            output_queue=None,
            on_status_change=MagicMock(),
            config=WorkerConfig(),
        )

        worker._report_benchmark()
