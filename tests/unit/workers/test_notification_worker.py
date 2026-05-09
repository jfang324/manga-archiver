from unittest.mock import MagicMock

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.workers.jobs import NotificationJob
from src.manga_archiver.workers.notification_worker import NotificationWorker
from src.manga_archiver.workers.types import JobMetadata, JobStatus


def _job_metadata() -> JobMetadata:
    return JobMetadata(
        chapter_id="job_123",
        manga_title="Test Manga",
        chapter_number=1.0,
        chapter_title="Chapter 1",
        app_config=AppConfig(),
        source=ContentSource.MANGADEX,
    )


class TestNotificationWorkerDoWork:
    @pytest.mark.asyncio
    async def test_do_work_passes_callback_args(self) -> None:
        mock_callback = MagicMock()
        worker = NotificationWorker(
            worker_id="test_notification_worker",
            input_queue=MagicMock(),
            on_status_update=mock_callback,
        )

        job = NotificationJob(
            id="job_123",
            metadata=_job_metadata(),
            start_time=1000,
            end_time=2000,
            status=JobStatus.COMPLETED,
        )

        mock_input_queue = MagicMock()
        mock_input_queue.get = MagicMock(return_value=job)
        worker._input_queue = mock_input_queue

        await worker._do_work(job)

        mock_callback.assert_called_once()
        args = mock_callback.call_args[0]
        assert args[0] == "job_123"
        assert args[1] == JobStatus.COMPLETED


@pytest.mark.parametrize(
    "status,should_set_completed_at",
    [
        (JobStatus.COMPLETED, True),
        (JobStatus.FAILED, True),
        (JobStatus.DOWNLOADING, False),
    ],
)
@pytest.mark.asyncio
async def test_do_work_completed_at_based_on_status(status, should_set_completed_at) -> None:
    mock_callback = MagicMock()
    worker = NotificationWorker(
        worker_id="test_notification_worker",
        input_queue=MagicMock(),
        on_status_update=mock_callback,
    )

    job = NotificationJob(
        id="job_123",
        metadata=_job_metadata(),
        status=status,
    )

    mock_input_queue = MagicMock()
    mock_input_queue.get = MagicMock(return_value=job)
    worker._input_queue = mock_input_queue

    await worker._do_work(job)

    args = mock_callback.call_args[0]
    metadata: JobMetadata = args[2]

    if should_set_completed_at:
        assert metadata.completed_at > 0
    else:
        assert metadata.completed_at == -1


@pytest.mark.parametrize("status", [JobStatus.COMPLETED, JobStatus.DOWNLOADING, JobStatus.MERGING])
@pytest.mark.asyncio
async def test_do_work_records_benchmark_timing(status) -> None:
    benchmark = MagicMock()
    mock_callback = MagicMock()
    worker = NotificationWorker(
        worker_id="test_notification_worker",
        input_queue=MagicMock(),
        on_status_update=mock_callback,
        benchmark=benchmark,
    )

    job = NotificationJob(
        id="job_123",
        metadata=_job_metadata(),
        status=status,
        start_time=1000,
        end_time=2000,
    )

    mock_input_queue = MagicMock()
    mock_input_queue.get = MagicMock(return_value=job)
    worker._input_queue = mock_input_queue

    await worker._do_work(job)

    benchmark.record.assert_called_once_with("job_123", status, 1000, 2000)
