from asyncio import Queue
from unittest.mock import MagicMock

from src.manga_archiver.workers import WorkerManager


class TestWorkerManagerInit:
    def test_creates_resolve_pool_with_correct_size(self):
        mock_provider_manager = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            num_resolve_workers=3,
            num_download_workers=4,
            num_merge_workers=2,
            num_upload_workers=1,
            benchmark_enabled=False,
            provider_manager=mock_provider_manager,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert len(manager.resolve_pool) == 3
        assert len(manager.download_pool) == 4
        assert len(manager.merge_pool) == 2
        assert len(manager.upload_pool) == 0

    def test_creates_upload_pool_when_google_drive_provided(self):
        mock_provider_manager = MagicMock()
        mock_download_client = MagicMock()
        mock_google_drive = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=2,
            benchmark_enabled=False,
            provider_manager=mock_provider_manager,
            download_client=mock_download_client,
            google_drive_client=mock_google_drive,
            on_status_update=mock_callback,
        )

        assert len(manager.upload_pool) == 2

    def test_creates_notification_worker(self):
        mock_provider_manager = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=False,
            provider_manager=mock_provider_manager,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert manager.notification_worker is not None

    def test_creates_benchmark_when_enabled(self):
        mock_provider_manager = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=Queue(),
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=True,
            provider_manager=mock_provider_manager,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert manager.notification_worker._benchmark is not None


class TestWorkerManagerWiring:
    def test_resolve_workers_wired_correctly(self):
        resolve_q = Queue()
        download_q = Queue()
        notify_q = Queue()
        mock_provider_manager = MagicMock()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=resolve_q,
            download_queue=download_q,
            merge_queue=Queue(),
            upload_queue=Queue(),
            notification_queue=notify_q,
            num_resolve_workers=2,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=False,
            provider_manager=mock_provider_manager,
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        for worker in manager.resolve_pool:
            assert worker._input_queue is resolve_q
            assert worker._output_queue is download_q
            assert worker._notification_queue is notify_q
            assert worker._provider_manager is mock_provider_manager

    def test_download_workers_wired_correctly(self):
        download_q = Queue()
        merge_q = Queue()
        notify_q = Queue()
        mock_download_client = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=download_q,
            merge_queue=merge_q,
            upload_queue=Queue(),
            notification_queue=notify_q,
            num_resolve_workers=1,
            num_download_workers=2,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=False,
            provider_manager=MagicMock(),
            download_client=mock_download_client,
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        for worker in manager.download_pool:
            assert worker._input_queue is download_q
            assert worker._output_queue is merge_q
            assert worker._notification_queue is notify_q
            assert worker._download_client is mock_download_client

    def test_merge_workers_wired_correctly(self):
        merge_q = Queue()
        upload_q = Queue()
        notify_q = Queue()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=merge_q,
            upload_queue=upload_q,
            notification_queue=notify_q,
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=2,
            num_upload_workers=0,
            benchmark_enabled=False,
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        for worker in manager.merge_pool:
            assert worker._input_queue is merge_q
            assert worker._output_queue is None
            assert worker._notification_queue is notify_q

    def test_upload_workers_wired_correctly_when_google_drive_enabled(self):
        upload_q = Queue()
        notify_q = Queue()
        mock_gdrive = MagicMock()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=Queue(),
            download_queue=Queue(),
            merge_queue=Queue(),
            upload_queue=upload_q,
            notification_queue=notify_q,
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=2,
            benchmark_enabled=False,
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            google_drive_client=mock_gdrive,
            on_status_update=mock_callback,
        )

        for worker in manager.upload_pool:
            assert worker._input_queue is upload_q
            assert worker._output_queue is None
            assert worker._notification_queue is notify_q
            assert worker._google_drive_client is mock_gdrive

    def test_notification_worker_receives_all_notifications(self):
        resolve_q = Queue()
        download_q = Queue()
        merge_q = Queue()
        notify_q = Queue()
        mock_callback = MagicMock()

        manager = WorkerManager(
            resolve_queue=resolve_q,
            download_queue=download_q,
            merge_queue=merge_q,
            upload_queue=Queue(),
            notification_queue=notify_q,
            num_resolve_workers=1,
            num_download_workers=1,
            num_merge_workers=1,
            num_upload_workers=0,
            benchmark_enabled=False,
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            google_drive_client=None,
            on_status_update=mock_callback,
        )

        assert manager.notification_worker._input_queue is notify_q
