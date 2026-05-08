import asyncio
from asyncio import Queue
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.integrations.exceptions import (
    NotFoundError,
    RateLimitError,
)
from src.manga_archiver.workers.base import Worker, WorkerConfig
from src.manga_archiver.workers.jobs import Job, JobStatus, NotificationJob
from src.manga_archiver.workers.scheduler import SchedulerFeedback


class ConcreteWorker(Worker):
    """Concrete implementation of Worker for testing."""

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        config: WorkerConfig,
        notification_queue: Queue,
        work_status: JobStatus = JobStatus.DOWNLOADING,
        scheduler_feedback_queue: Queue[SchedulerFeedback] | None = None,
    ) -> None:
        super().__init__(
            worker_id,
            input_queue,
            output_queue,
            config,
            notification_queue,
            work_status,
            scheduler_feedback_queue,
        )

    async def _do_work(self, job: Job) -> Job | None:  # noqa: ARG002
        return None


def _notifications(mock_notification_queue: AsyncMock) -> list[NotificationJob]:
    return [call_args[0][0] for call_args in mock_notification_queue.put.call_args_list]


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


class TestRetryLogic:
    @pytest.mark.asyncio
    async def test_run_marks_job_done_when_processing_is_cancelled(self, mock_job) -> None:
        input_queue = asyncio.Queue()
        await input_queue.put(mock_job)

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=input_queue,
            output_queue=MagicMock(),
            config=WorkerConfig(),
            notification_queue=AsyncMock(),
        )

        worker._do_work = AsyncMock(side_effect=asyncio.CancelledError)

        await worker.run()

        await asyncio.wait_for(input_queue.join(), timeout=0.1)

    @pytest.mark.parametrize(
        "error",
        [
            NotFoundError("404"),
            ValueError("Simulated failure"),
            RuntimeError("Unexpected"),
        ],
        ids=["not_found", "validation_error", "unexpected_error"],
    )
    @pytest.mark.asyncio
    async def test_fail_fast_errors_send_phase_start_and_failed(
        self, mock_job, error: Exception
    ) -> None:
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=MagicMock(),
            config=WorkerConfig(max_retries=3, base_delay=0),
            notification_queue=mock_notification_queue,
        )
        worker._do_work = AsyncMock(side_effect=error)

        await worker._process_job(mock_job)

        worker._do_work.assert_awaited_once_with(mock_job)
        notifications = _notifications(mock_notification_queue)
        assert [notification.status for notification in notifications] == [
            JobStatus.DOWNLOADING,
            JobStatus.FAILED,
        ]
        assert notifications[0].start_time > 0
        assert notifications[0].end_time == -1

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
        assert mock_notification_queue.put.call_count == 2
        notifications = _notifications(mock_notification_queue)
        assert notifications[0].status == JobStatus.DOWNLOADING
        assert notifications[1].status == JobStatus.FAILED

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
    async def test_negative_max_retries_still_processes_job_once(self, mock_job) -> None:
        config = WorkerConfig(max_retries=-1, base_delay=0)
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=None,
            config=config,
            notification_queue=mock_notification_queue,
        )
        worker._do_work = AsyncMock(return_value=None)

        await worker._process_job(mock_job)

        worker._do_work.assert_awaited_once_with(mock_job)
        notifications = _notifications(mock_notification_queue)
        assert [notification.status for notification in notifications] == [
            JobStatus.DOWNLOADING,
            JobStatus.DOWNLOADING,
            JobStatus.COMPLETED,
        ]

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

        assert mock_notification_queue.put.call_count == 2
        notifications = _notifications(mock_notification_queue)
        assert notifications[0].status == JobStatus.DOWNLOADING
        call_args = notifications[1]
        assert call_args.status == JobStatus.FAILED

    @pytest.mark.asyncio
    async def test_successful_terminal_job_sends_phase_timing_and_completed(self, mock_job) -> None:
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=None,
            config=WorkerConfig(),
            notification_queue=mock_notification_queue,
            work_status=JobStatus.MERGING,
        )

        await worker._process_job(mock_job)

        notifications = _notifications(mock_notification_queue)
        assert [notification.status for notification in notifications] == [
            JobStatus.MERGING,
            JobStatus.MERGING,
            JobStatus.COMPLETED,
        ]
        assert notifications[0].start_time > 0
        assert notifications[0].end_time == -1
        assert notifications[1].start_time == notifications[0].start_time
        assert notifications[1].end_time >= notifications[1].start_time

    @pytest.mark.asyncio
    async def test_successful_non_terminal_job_sends_phase_timing_and_enqueues_next_job(
        self, mock_job
    ) -> None:
        mock_notification_queue = AsyncMock()
        output_queue: Queue[Job] = Queue()
        next_job = mock_job

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=output_queue,
            config=WorkerConfig(),
            notification_queue=mock_notification_queue,
            work_status=JobStatus.DOWNLOADING,
        )
        worker._do_work = AsyncMock(return_value=next_job)

        await worker._process_job(mock_job)

        notifications = _notifications(mock_notification_queue)
        assert [notification.status for notification in notifications] == [
            JobStatus.DOWNLOADING,
            JobStatus.DOWNLOADING,
        ]
        assert await output_queue.get() is next_job

    @pytest.mark.asyncio
    async def test_rate_limit_retry_keeps_single_phase_measurement(self, mock_job) -> None:
        mock_notification_queue = AsyncMock()

        worker = ConcreteWorker(
            worker_id="test_worker",
            input_queue=MagicMock(),
            output_queue=None,
            config=WorkerConfig(max_retries=1, base_delay=0),
            notification_queue=mock_notification_queue,
            work_status=JobStatus.FETCHING_RESOURCES,
        )
        worker._do_work = AsyncMock(side_effect=[RateLimitError("429"), None])

        await worker._process_job(mock_job)

        notifications = _notifications(mock_notification_queue)
        assert [notification.status for notification in notifications] == [
            JobStatus.FETCHING_RESOURCES,
            JobStatus.FETCHING_RESOURCES,
            JobStatus.COMPLETED,
        ]
        assert notifications[1].start_time == notifications[0].start_time
        assert notifications[1].end_time >= notifications[0].start_time
