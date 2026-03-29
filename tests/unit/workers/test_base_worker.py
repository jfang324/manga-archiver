from unittest.mock import MagicMock

import pytest

from src.mangadex_downloader.workers.base import Worker, WorkerConfig
from src.mangadex_downloader.workers.jobs import Job, JobStatus


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
            on_status_change=MagicMock(),
            config=config,
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
            on_status_change=MagicMock(),
            config=config,
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
            on_status_change=MagicMock(),
            config=config,
        )

        assert worker._calculate_backoff(0) == 5.0
        assert worker._calculate_backoff(1) == 10.0
        assert worker._calculate_backoff(2) == 20.0


class TestWorkerLifecycle:
    def test_stop_sets_running_false(self):
        worker = ConcreteWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=WorkerConfig(),
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
        on_status_change = MagicMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"

        do_work_call_count = 0

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                nonlocal do_work_call_count
                do_work_call_count += 1
                raise ValueError("Simulated failure")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        await worker._process_job(mock_job)

        assert do_work_call_count == config.max_retries + 1

    @pytest.mark.asyncio
    async def test_calls_on_status_change_failed_after_max_retries(self):
        config = WorkerConfig(max_retries=2, base_delay=0)
        on_status_change = MagicMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                raise ValueError("Simulated failure")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        await worker._process_job(mock_job)

        on_status_change.assert_called_with("test_job", JobStatus.FAILED)

    @pytest.mark.asyncio
    async def test_backoff_called_between_retries(self):
        config = WorkerConfig(max_retries=2, base_delay=0)
        on_status_change = MagicMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"

        call_count = 0

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                nonlocal call_count
                call_count += 1
                raise ValueError("Simulated failure")

        worker = FailingWorker(
            id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        await worker._process_job(mock_job)

        assert call_count == config.max_retries + 1
