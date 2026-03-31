from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.mangadex_downloader.enums import JobStatus
from src.mangadex_downloader.workers.base import Worker, WorkerConfig
from src.mangadex_downloader.workers.jobs import Job


class ConcreteWorker(Worker):
    """Concrete implementation of Worker for testing."""

    async def _do_work(self, job: Job) -> Job | None:
        return None


class TestBackoffCalculation:
    def test_exponential_backoff_no_jitter(self):
        config = WorkerConfig(
            max_retries=5, base_delay=2, jitter=False, await_output_space=False
        )
        worker = ConcreteWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        # Test backoff for attempts 0-4: 2, 4, 8, 16, 32
        assert worker._calculate_backoff(0) == 2.0
        assert worker._calculate_backoff(1) == 4.0
        assert worker._calculate_backoff(2) == 8.0
        assert worker._calculate_backoff(3) == 16.0
        assert worker._calculate_backoff(4) == 32.0

    def test_exponential_backoff_with_jitter(self):
        config = WorkerConfig(
            max_retries=5, base_delay=2, jitter=True, await_output_space=False
        )
        worker = ConcreteWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        backoff = worker._calculate_backoff(0)
        assert 2.0 <= backoff <= 2.2

        backoff = worker._calculate_backoff(1)
        assert 4.0 <= backoff <= 4.4

    def test_backoff_uses_config_values(self):
        config = WorkerConfig(
            max_retries=5, base_delay=5, jitter=False, await_output_space=False
        )
        worker = ConcreteWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        assert worker._calculate_backoff(0) == 5.0
        assert worker._calculate_backoff(1) == 10.0
        assert worker._calculate_backoff(2) == 20.0

    def test_stop_sets_running_false(self):
        worker = ConcreteWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=WorkerConfig(),
            notification_queue=AsyncMock(),
        )

        # Initially running should be False (set in __init__)
        assert worker._running is False

        # Set to True to simulate running
        worker._running = True
        assert worker._running is True

        # Stop should set it back to False
        worker.stop()
        assert worker._running is False


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_retries_up_to_max_retries(self):
        config = WorkerConfig(max_retries=3, base_delay=0)

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"
        mock_job.manga_title = "Test Manga"
        mock_job.chapter_title = "Chapter 1"
        mock_job.output_directory = MagicMock()
        mock_job.output_format = MagicMock()
        mock_job.start_time = -1
        mock_job.end_time = -1

        do_work_call_count = 0

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                nonlocal do_work_call_count
                do_work_call_count += 1
                raise TimeoutError("Simulated timeout")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        await worker._process_job(mock_job)

        assert do_work_call_count == config.max_retries + 1

    @pytest.mark.asyncio
    async def test_posts_failed_status_to_notification_queue_on_fail(self):
        config = WorkerConfig(max_retries=2, base_delay=0)

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"
        mock_job.manga_title = "Test Manga"
        mock_job.chapter_title = "Chapter 1"
        mock_job.output_directory = MagicMock()
        mock_job.output_format = MagicMock()
        mock_job.start_time = -1
        mock_job.end_time = -1

        mock_notification_queue = AsyncMock()

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                raise ValueError("Simulated failure")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        await worker._process_job(mock_job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_backoff_called_between_retries(self):
        config = WorkerConfig(max_retries=2, base_delay=0)

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"
        mock_job.manga_title = "Test Manga"
        mock_job.chapter_title = "Chapter 1"
        mock_job.output_directory = MagicMock()
        mock_job.output_format = MagicMock()
        mock_job.start_time = -1
        mock_job.end_time = -1

        call_count = 0

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                nonlocal call_count
                call_count += 1
                raise TimeoutError("Simulated timeout")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        mock_calculate_backoff = MagicMock(return_value=0.1)

        with patch(
            "src.mangadex_downloader.workers.base.Worker._calculate_backoff",
            mock_calculate_backoff,
        ):
            await worker._process_job(mock_job)

            assert call_count == config.max_retries + 1
            assert mock_calculate_backoff.call_count == config.max_retries
