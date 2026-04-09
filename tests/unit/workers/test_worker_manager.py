from asyncio import Queue, Semaphore
from unittest.mock import MagicMock

from src.manga_archiver.workers import WorkerManager


class TestWorkerManagerInit:
    def test_creates_resolve_pool_with_correct_size(self):
        mock_api_client = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            resolve_semaphore=Semaphore(5),
            download_semaphore=Semaphore(10),
            num_resolve_workers=3,
            num_download_workers=4,
            num_merge_workers=2,
            num_upload_workers=1,
            benchmark_enabled=False,
            mangadex_api_client=mock_api_client,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert len(manager.resolve_pool) == 3
        assert len(manager.download_pool) == 4
        assert len(manager.merge_pool) == 2
        assert len(manager.upload_pool) == 0

    def test_creates_upload_pool_when_google_drive_provided(self):
        mock_api_client = MagicMock()
        mock_download_client = MagicMock()
        mock_google_drive = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            resolve_semaphore=Semaphore(5),
            download_semaphore=Semaphore(10),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=2,
            benchmark_enabled=False,
            mangadex_api_client=mock_api_client,
            download_client=mock_download_client,
            google_drive_client=mock_google_drive,
            on_status_update=mock_callback,
        )

        assert len(manager.upload_pool) == 2

    def test_creates_notification_worker(self):
        mock_api_client = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            resolve_semaphore=Semaphore(5),
            download_semaphore=Semaphore(10),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=False,
            mangadex_api_client=mock_api_client,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert manager.notification_worker is not None

    def test_creates_benchmark_when_enabled(self):
        mock_api_client = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            resolve_semaphore=Semaphore(5),
            download_semaphore=Semaphore(10),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=True,
            mangadex_api_client=mock_api_client,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert manager.notification_worker._benchmark is not None
