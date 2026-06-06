from asyncio import Queue
from unittest.mock import MagicMock, patch

from src.manga_archiver.integrations.storage_providers.google_drive import GoogleDriveFolderCache
from src.manga_archiver.persistence.google_drive_token_store import GoogleApiStoredToken
from src.manga_archiver.pipeline import PipelineConfig
from src.manga_archiver.pipeline.queues import PipelineQueues
from src.manga_archiver.pipeline.worker_manager import WorkerManager


def _token() -> GoogleApiStoredToken:
    return {
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


def _queues(
    *,
    resolve: Queue | None = None,
    download: Queue | None = None,
    merge: Queue | None = None,
    upload: Queue | None = None,
    notification: Queue | None = None,
) -> PipelineQueues:
    """Build a PipelineQueues with sensible per-test defaults."""
    return PipelineQueues(
        resolve=resolve if resolve is not None else Queue(),
        download=download if download is not None else Queue(),
        merge=merge if merge is not None else Queue(),
        upload=upload if upload is not None else Queue(),
        notification=notification if notification is not None else Queue(),
    )


def _created_folder_caches(
    mock_google_drive_archive_store: MagicMock,
) -> list[GoogleDriveFolderCache]:
    return [call.kwargs["folder_cache"] for call in mock_google_drive_archive_store.call_args_list]


def _initialized_google_drive_folder_cache() -> GoogleDriveFolderCache:
    folder_cache = GoogleDriveFolderCache()
    folder_cache.root_folder_id = "root_123"

    return folder_cache


class TestWorkerManagerInit:
    def test_creates_resolve_pool_with_correct_size(self) -> None:
        manager = WorkerManager(
            queues=_queues(),
            config=PipelineConfig(
                num_resolve_workers=3,
                num_download_workers=4,
                num_merge_workers=2,
                num_upload_workers=1,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
        )

        assert len(manager.resolve_pool) == 3
        assert len(manager.download_pool) == 4
        assert len(manager.merge_pool) == 2
        assert len(manager.upload_pool) == 0

    def test_exposes_benchmark_aggregates_when_enabled(self) -> None:
        manager = WorkerManager(
            queues=_queues(),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=1,
                num_merge_workers=1,
                num_upload_workers=0,
                benchmark_enabled=True,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
        )

        aggregates = manager.get_benchmark_aggregates()
        assert aggregates is not None
        assert aggregates.total_job_count == 0


class TestWorkerManagerWiring:
    def test_resolve_workers_wired_correctly(self) -> None:
        resolve_q = Queue()
        download_q = Queue()
        notify_q = Queue()
        mock_provider_manager = MagicMock()

        manager = WorkerManager(
            queues=_queues(resolve=resolve_q, download=download_q, notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=2,
                num_download_workers=1,
                num_merge_workers=1,
                num_upload_workers=0,
            ),
            provider_manager=mock_provider_manager,
            download_client=MagicMock(),
            on_status_update=MagicMock(),
        )

        for worker in manager.resolve_pool:
            assert worker._input_queue is resolve_q
            assert worker._output_queue is download_q
            assert worker._notification_queue is notify_q
            assert worker._provider_manager is mock_provider_manager

    def test_download_workers_wired_correctly(self) -> None:
        download_q = Queue()
        merge_q = Queue()
        notify_q = Queue()
        mock_download_client = MagicMock()

        manager = WorkerManager(
            queues=_queues(download=download_q, merge=merge_q, notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=2,
                num_merge_workers=1,
                num_upload_workers=0,
            ),
            provider_manager=MagicMock(),
            download_client=mock_download_client,
            on_status_update=MagicMock(),
        )

        for worker in manager.download_pool:
            assert worker._input_queue is download_q
            assert worker._output_queue is merge_q
            assert worker._notification_queue is notify_q
            assert worker._download_client is mock_download_client

    def test_merge_workers_wired_correctly(self) -> None:
        merge_q = Queue()
        upload_q = Queue()
        notify_q = Queue()

        manager = WorkerManager(
            queues=_queues(merge=merge_q, upload=upload_q, notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=1,
                num_merge_workers=2,
                num_upload_workers=0,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
        )

        for worker in manager.merge_pool:
            assert worker._input_queue is merge_q
            assert worker._output_queue is None
            assert worker._notification_queue is notify_q

    @patch("src.manga_archiver.pipeline.worker_manager.GoogleDriveArchiveStore")
    def test_upload_workers_wired_correctly_when_google_drive_enabled(
        self, mock_google_drive_archive_store: MagicMock
    ) -> None:
        upload_q = Queue()
        notify_q = Queue()
        clients = [MagicMock(), MagicMock()]
        mock_google_drive_archive_store.side_effect = clients
        folder_cache = _initialized_google_drive_folder_cache()

        manager = WorkerManager(
            queues=_queues(upload=upload_q, notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=1,
                num_merge_workers=1,
                num_upload_workers=2,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
            google_drive_token=_token(),
            google_drive_folder_cache=folder_cache,
        )

        assert manager.upload_pool[0]._google_drive_archive_store is clients[0]
        assert manager.upload_pool[1]._google_drive_archive_store is clients[1]
        first_cache, second_cache = _created_folder_caches(mock_google_drive_archive_store)
        assert first_cache is folder_cache
        assert second_cache is first_cache

        for worker in manager.upload_pool:
            assert worker._input_queue is upload_q
            assert worker._output_queue is None
            assert worker._notification_queue is notify_q

    @patch("src.manga_archiver.pipeline.worker_manager.GoogleDriveArchiveStore")
    def test_merge_workers_route_to_upload_queue_when_google_drive_enabled(
        self, mock_google_drive_archive_store: MagicMock
    ) -> None:
        merge_q = Queue()
        upload_q = Queue()
        notify_q = Queue()
        folder_cache = _initialized_google_drive_folder_cache()

        manager = WorkerManager(
            queues=_queues(merge=merge_q, upload=upload_q, notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=1,
                num_merge_workers=2,
                num_upload_workers=1,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
            google_drive_token=_token(),
            google_drive_folder_cache=folder_cache,
        )

        for worker in manager.merge_pool:
            assert worker._input_queue is merge_q
            assert worker._output_queue is upload_q
        mock_google_drive_archive_store.assert_called_once()
        assert mock_google_drive_archive_store.call_args.args == (_token(),)
        assert mock_google_drive_archive_store.call_args.kwargs["folder_cache"] is folder_cache

    def test_notification_worker_receives_all_notifications(self) -> None:
        notify_q = Queue()

        manager = WorkerManager(
            queues=_queues(notification=notify_q),
            config=PipelineConfig(
                num_resolve_workers=1,
                num_download_workers=1,
                num_merge_workers=1,
                num_upload_workers=0,
            ),
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            on_status_update=MagicMock(),
        )

        assert manager.notification_worker._input_queue is notify_q
