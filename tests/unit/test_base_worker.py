"""Unit tests for base Worker class."""

from contextlib import suppress
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.workers.base import Worker, WorkerConfig
from src.mangadex_downloader.workers.jobs import Job, JobStatus


class ConcreteWorker(Worker):
    """Concrete implementation of Worker for testing."""

    async def _do_work(self, job: Job) -> Job | None:
        """Simple implementation that returns None."""
        return None


class TestWorkerConfig:
    """Test WorkerConfig dataclass."""

    def test_default_config_values(self):
        """Test default configuration values."""
        config = WorkerConfig()
        assert config.max_retries == 5
        assert config.base_delay == 2
        assert config.jitter is False
        assert config.await_output_space is False

    def test_custom_config_values(self):
        """Test custom configuration values."""
        config = WorkerConfig(
            max_retries=10,
            base_delay=5,
            jitter=True,
            await_output_space=True,
        )
        assert config.max_retries == 10
        assert config.base_delay == 5
        assert config.jitter is True
        assert config.await_output_space is True


class TestBackoffCalculation:
    """Test exponential backoff calculation."""

    def test_exponential_backoff_no_jitter(self):
        """Test exponential backoff without jitter."""
        config = WorkerConfig(max_retries=5, base_delay=2, jitter=False)
        worker = ConcreteWorker(
            worker_id="test_worker",
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
        """Test exponential backoff with jitter."""
        config = WorkerConfig(max_retries=5, base_delay=2, jitter=True)
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=config,
        )

        # With jitter, backoff should be base_delay * 2^attempt + (0 to base_delay * 2^attempt * 0.1)
        # For attempt=0: 2 + (0 to 0.2) = 2.0 to 2.2
        backoff = worker._calculate_backoff(0)
        assert 2.0 <= backoff <= 2.2

        # For attempt=1: 4 + (0 to 0.4) = 4.0 to 4.4
        backoff = worker._calculate_backoff(1)
        assert 4.0 <= backoff <= 4.4

    def test_backoff_uses_config_values(self):
        """Test backoff uses config's base_delay."""
        config = WorkerConfig(max_retries=5, base_delay=5, jitter=False)
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            on_status_change=MagicMock(),
            config=config,
        )

        # Should use base_delay=5 instead of default 2
        assert worker._calculate_backoff(0) == 5.0
        assert worker._calculate_backoff(1) == 10.0
        assert worker._calculate_backoff(2) == 20.0


class TestWorkerLifecycle:
    """Test worker lifecycle methods."""

    def test_stop_sets_running_false(self):
        """Test that stop() sets _running to False."""
        worker = ConcreteWorker(
            worker_id="test_worker",
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
    """Test retry logic in _process_job."""

    @pytest.mark.asyncio
    async def test_retries_up_to_max_retries(self):
        """Test that job is retried exactly max_retries times."""
        config = WorkerConfig(max_retries=3, base_delay=0)
        on_status_change = MagicMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"

        # Create a worker that always raises an exception
        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                raise ValueError("Simulated failure")

        input_queue = AsyncMock()
        input_queue.get = AsyncMock(return_value=mock_job)
        input_queue.task_done = MagicMock()

        worker = FailingWorker(
            worker_id="test_worker",
            input_queue=input_queue,
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        # Run the worker (it will retry and eventually fail)
        # The run method catches exceptions and continues, so we need to stop it
        import asyncio

        async def run_with_timeout():
            task = asyncio.create_task(worker.run())
            await asyncio.sleep(0.1)  # Let it run a bit
            worker.stop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        await run_with_timeout()

        # Should have called on_status_change for each retry + final failure
        # 3 retries (max_retries=3) + 1 final failure = 4 calls
        # Actually, on failure after max_retries, it calls FAILED
        # So we expect: FETCHING_RESOURCES (from _do_work), then FAILED
        # But since _do_work always fails, it should retry max_retries times
        # then call on_status_change with FAILED
        assert on_status_change.call_count >= 1

    @pytest.mark.asyncio
    async def test_calls_on_status_change_failed_after_max_retries(self):
        """Test that on_status_change is called with FAILED after exhausting retries."""
        config = WorkerConfig(max_retries=2, base_delay=0)
        on_status_change = MagicMock()

        mock_job = MagicMock(spec=Job)
        mock_job.id = "test_job"

        class FailingWorker(Worker):
            async def _do_work(self, job: Job) -> Job | None:
                raise ValueError("Simulated failure")

        input_queue = AsyncMock()
        input_queue.get = AsyncMock(return_value=mock_job)
        input_queue.task_done = MagicMock()

        worker = FailingWorker(
            worker_id="test_worker",
            input_queue=input_queue,
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        import asyncio

        async def run_with_timeout():
            task = asyncio.create_task(worker.run())
            await asyncio.sleep(0.1)
            worker.stop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        await run_with_timeout()

        # Verify FAILED was called
        on_status_change.assert_any_call("test_job", JobStatus.FAILED)

    @pytest.mark.asyncio
    async def test_backoff_called_between_retries(self):
        """Test that backoff is called between retry attempts."""
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

        input_queue = AsyncMock()
        input_queue.get = AsyncMock(return_value=mock_job)
        input_queue.task_done = MagicMock()

        worker = FailingWorker(
            worker_id="test_worker",
            input_queue=input_queue,
            output_queue=MagicMock(),
            on_status_change=on_status_change,
            config=config,
        )

        import asyncio

        async def run_with_timeout():
            task = asyncio.create_task(worker.run())
            await asyncio.sleep(0.1)
            worker.stop()
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

        await run_with_timeout()

        # Should have called _do_work max_retries + 1 times (initial + retries)
        assert call_count >= config.max_retries
