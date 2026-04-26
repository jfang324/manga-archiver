from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.integrations.exceptions import (
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.workers.base import Worker, WorkerConfig
from src.manga_archiver.workers.jobs import Job, JobStatus


class ConcreteWorker(Worker):
    """Concrete implementation of Worker for testing."""

    async def _do_work(self, job: Job) -> Job | None:  # noqa: ARG002
        return None


class TestBackoffCalculation:
    def test_exponential_backoff_no_jitter(self) -> None:
        config = WorkerConfig(max_retries=5, base_delay=2, jitter=False, await_output_space=False)
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        assert worker._calculate_backoff(0) == 2.0
        assert worker._calculate_backoff(1) == 4.0
        assert worker._calculate_backoff(2) == 8.0
        assert worker._calculate_backoff(3) == 16.0
        assert worker._calculate_backoff(4) == 32.0

    def test_exponential_backoff_with_jitter(self) -> None:
        config = WorkerConfig(max_retries=5, base_delay=2, jitter=True, await_output_space=False)
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        backoff = worker._calculate_backoff(0)
        assert 2.0 <= backoff <= 2.2

        backoff = worker._calculate_backoff(1)
        assert 4.0 <= backoff <= 4.4

    def test_backoff_uses_config_values(self) -> None:
        config = WorkerConfig(max_retries=5, base_delay=5, jitter=False, await_output_space=False)
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        assert worker._calculate_backoff(0) == 5.0
        assert worker._calculate_backoff(1) == 10.0
        assert worker._calculate_backoff(2) == 20.0

    def test_stop_sets_running_false(self) -> None:
        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=WorkerConfig(),
            notification_queue=AsyncMock(),
        )

        worker._running = True
        worker.stop()
        assert worker._running is False


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_not_found_error_fails_immediately(self, mock_job) -> None:
        config = WorkerConfig(max_retries=3, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        worker._do_work = AsyncMock(side_effect=NotFoundError("404"))

        await worker._process_job(mock_job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_rate_limit_error_retries_then_fails(self, mock_job) -> None:
        config = WorkerConfig(max_retries=2, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        call_count = 0

        async def mock_do_work(job) -> None:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            raise RateLimitError("429")

        worker._do_work = mock_do_work

        await worker._process_job(mock_job)

        assert call_count == config.max_retries + 1
        mock_notification_queue.put.assert_called_once()
        assert mock_notification_queue.put.call_args[0][0].status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_backoff_called_between_retries(self, mock_job) -> None:
        config = WorkerConfig(max_retries=2, base_delay=0)

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        call_count = 0

        async def mock_do_work(job) -> None:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Simulated timeout")

        worker._do_work = mock_do_work
        mock_calculate_backoff = MagicMock(return_value=0.1)

        with patch(
            "src.manga_archiver.workers.base.Worker._calculate_backoff",
            mock_calculate_backoff,
        ):
            await worker._process_job(mock_job)

            assert call_count == config.max_retries + 1
            assert mock_calculate_backoff.call_count == config.max_retries

    @pytest.mark.asyncio
    async def test_retries_on_transient_errors(self, mock_job) -> None:
        config = WorkerConfig(max_retries=3, base_delay=0)

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=AsyncMock(),
        )

        call_count = 0

        async def mock_do_work(job) -> None:  # noqa: ARG001
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Simulated timeout")

        worker._do_work = mock_do_work
        await worker._process_job(mock_job)

        assert call_count == config.max_retries + 1

    @pytest.mark.asyncio
    async def test_posts_failed_status_on_transient_error(self, mock_job) -> None:
        config = WorkerConfig(max_retries=3, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        worker._do_work = AsyncMock(side_effect=TimeoutError("Simulated timeout"))

        await worker._process_job(mock_job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_fails_immediately_on_non_transient_errors(self, mock_job) -> None:
        config = WorkerConfig(max_retries=3, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        worker._do_work = AsyncMock(side_effect=ValueError("Simulated failure"))

        await worker._process_job(mock_job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_generic_exception_fails_immediately(self, mock_job) -> None:
        config = WorkerConfig(max_retries=3, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=config,
            notification_queue=mock_notification_queue,
        )

        worker._do_work = AsyncMock(side_effect=RuntimeError("Unexpected"))

        await worker._process_job(mock_job)

        mock_notification_queue.put.assert_called_once()
        call_args = mock_notification_queue.put.call_args[0][0]
        assert call_args.status == JobStatus.FAILED
