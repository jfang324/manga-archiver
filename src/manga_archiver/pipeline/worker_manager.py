import asyncio
import logging
from asyncio import Queue
from collections.abc import Callable

from ..integrations.content_providers import ContentProviderManager
from ..integrations.storage_providers.google_drive import (
    GoogleDriveArchiveStore,
    GoogleDriveFolderCache,
)
from ..integrations.storage_providers.google_drive.types import GoogleApiStoredToken
from ..utils import DownloadClient, MultiFormatExporter
from ..workers.base import WorkerConfig
from ..workers.download_worker import DownloadWorker
from ..workers.jobs import Job, NotificationJob
from ..workers.merge_worker import MergeWorker
from ..workers.notification_worker import BenchmarkManager, NotificationWorker
from ..workers.resolve_worker import ResolveWorker
from ..workers.scheduler import SchedulerFeedback
from ..workers.types import JobMetadata, JobStatus
from ..workers.upload_worker import UploadWorker

logger = logging.getLogger(__name__)


class WorkerManager:
    """Manages worker pools and their lifecycle.

    Responsible for creating and orchestrating all worker pools:
    - Resolve workers (fetch chapter resources from provider manager)
    - Download workers (download images)
    - Merge workers (create PDF/CBZ/EPUB)
    - Upload workers (upload to cloud storage)
    - Notification worker (track job status)
    """

    def __init__(
        self,
        resolve_queue: Queue[Job],
        download_queue: Queue[Job],
        merge_queue: Queue[Job],
        upload_queue: Queue[Job],
        notification_queue: Queue[NotificationJob],
        num_resolve_workers: int,
        num_download_workers: int,
        num_merge_workers: int,
        num_upload_workers: int,
        benchmark_enabled: bool,
        provider_manager: ContentProviderManager,
        download_client: DownloadClient,
        google_drive_token: GoogleApiStoredToken | None,
        on_status_update: Callable[[str, JobStatus, JobMetadata], None],
        google_drive_folder_cache: GoogleDriveFolderCache | None = None,
        resolve_scheduler_feedback_queue: Queue[SchedulerFeedback] | None = None,
    ) -> None:
        """Initialize the worker manager.

        Args:
            resolve_queue: Queue for resolve jobs
            download_queue: Queue for download jobs
            merge_queue: Queue for merge jobs
            upload_queue: Queue for upload jobs
            notification_queue: Queue for notification jobs
            num_resolve_workers: Number of resolve workers to create
            num_download_workers: Number of download workers to create
            num_merge_workers: Number of merge workers to create
            num_upload_workers: Number of upload workers to create
            benchmark_enabled: Whether to enable benchmarking
            provider_manager: Content provider manager
            download_client: Client for downloading images
            google_drive_token: Token for creating Google Drive upload clients
            google_drive_folder_cache: Shared cache for upload clients
            on_status_update: Callback for status updates
            resolve_scheduler_feedback_queue: Optional queue for resolve scheduler feedback
        """
        self._resolve_pool: list[ResolveWorker] = [
            ResolveWorker(
                worker_id=f"resolve_worker_{index}",
                input_queue=resolve_queue,
                output_queue=download_queue,
                notification_queue=notification_queue,
                config=WorkerConfig(),
                provider_manager=provider_manager,
                scheduler_feedback_queue=resolve_scheduler_feedback_queue,
            )
            for index in range(num_resolve_workers)
        ]

        self._download_pool: list[DownloadWorker] = [
            DownloadWorker(
                worker_id=f"download_worker_{index}",
                input_queue=download_queue,
                output_queue=merge_queue,
                notification_queue=notification_queue,
                config=WorkerConfig(),
                download_client=download_client,
                provider_manager=provider_manager,
            )
            for index in range(num_download_workers)
        ]

        self._merge_pool: list[MergeWorker] = [
            MergeWorker(
                worker_id=f"merge_worker_{index}",
                input_queue=merge_queue,
                output_queue=upload_queue if google_drive_token else None,
                notification_queue=notification_queue,
                config=WorkerConfig(),
                multi_format_exporter=MultiFormatExporter(),
            )
            for index in range(num_merge_workers)
        ]

        self._upload_pool: list[UploadWorker] = []

        if google_drive_token:
            if (
                google_drive_folder_cache is None
                or google_drive_folder_cache.root_folder_id is None
            ):
                raise ValueError("Google Drive folder cache is not initialized")

            self._upload_pool = [
                UploadWorker(
                    worker_id=f"upload_worker_{index}",
                    input_queue=upload_queue,
                    output_queue=None,
                    notification_queue=notification_queue,
                    config=WorkerConfig(),
                    google_drive_archive_store=GoogleDriveArchiveStore(
                        google_drive_token, folder_cache=google_drive_folder_cache
                    ),
                )
                for index in range(num_upload_workers)
            ]

        self._notification_worker = NotificationWorker(
            worker_id="notification_worker",
            input_queue=notification_queue,
            on_status_update=on_status_update,
            benchmark=BenchmarkManager() if benchmark_enabled else None,
        )

    @property
    def resolve_pool(self) -> list[ResolveWorker]:
        """Get the resolve worker pool."""
        return self._resolve_pool

    @property
    def download_pool(self) -> list[DownloadWorker]:
        """Get the download worker pool."""
        return self._download_pool

    @property
    def merge_pool(self) -> list[MergeWorker]:
        """Get the merge worker pool."""
        return self._merge_pool

    @property
    def upload_pool(self) -> list[UploadWorker]:
        """Get the upload worker pool."""
        return self._upload_pool

    @property
    def notification_worker(self) -> NotificationWorker:
        """Get the notification worker."""
        return self._notification_worker

    async def start(self) -> None:
        """Start all workers in the pipeline."""
        all_workers = (
            [self._notification_worker]
            + self._resolve_pool
            + self._download_pool
            + self._merge_pool
            + self._upload_pool
        )

        await asyncio.gather(*[w.run() for w in all_workers])

    def stop(self) -> None:
        """Stop all workers in the pipeline."""
        for worker in (
            [self._notification_worker]
            + self._resolve_pool
            + self._download_pool
            + self._merge_pool
            + self._upload_pool
        ):
            worker.stop()
