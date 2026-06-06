from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TYPE_CHECKING

from ..integrations.content_providers import ContentProviderManager
from ..integrations.storage_providers.google_drive import (
    GoogleDriveArchiveStore,
    GoogleDriveFolderCache,
)
from ..utils import DownloadClient, MultiFormatExporter
from ..workers.base import WorkerConfig
from ..workers.download_worker import DownloadWorker
from ..workers.merge_worker import MergeWorker
from ..workers.notification_worker import NotificationWorker
from ..workers.resolve_worker import ResolveWorker
from ..workers.types import JobMetadata, JobStatus
from ..workers.upload_worker import UploadWorker
from .benchmark import BenchmarkAggregates, BenchmarkManager
from .queues import PipelineQueues

if TYPE_CHECKING:
    from ..persistence.google_drive_token_store import GoogleApiStoredToken
    from .manager import PipelineConfig

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
        queues: PipelineQueues,
        config: PipelineConfig,
        provider_manager: ContentProviderManager,
        download_client: DownloadClient,
        on_status_update: Callable[[str, JobStatus, JobMetadata], None],
        google_drive_token: GoogleApiStoredToken | None = None,
        google_drive_folder_cache: GoogleDriveFolderCache | None = None,
    ) -> None:
        """Initialize the worker manager.

        Args:
            queues: The queue topology connecting the worker stages
            config: The pipeline configuration (worker counts, benchmark flag, etc.)
            provider_manager: The content provider manager (used by resolve and download workers)
            download_client: The client for downloading images (used by download workers)
            on_status_update: Callback for status updates
            google_drive_token: Optional token for creating Google Drive upload clients
            google_drive_folder_cache: Shared cache for upload clients, required with google_drive_token
        """
        self._resolve_pool: list[ResolveWorker] = [
            ResolveWorker(
                worker_id=f"resolve_worker_{index}",
                input_queue=queues.resolve,
                output_queue=queues.download,
                notification_queue=queues.notification,
                config=WorkerConfig(),
                provider_manager=provider_manager,
                scheduler_feedback_queue=queues.resolve_scheduler_feedback,
            )
            for index in range(config.num_resolve_workers)
        ]

        self._download_pool: list[DownloadWorker] = [
            DownloadWorker(
                worker_id=f"download_worker_{index}",
                input_queue=queues.download,
                output_queue=queues.merge,
                notification_queue=queues.notification,
                config=WorkerConfig(),
                download_client=download_client,
                provider_manager=provider_manager,
            )
            for index in range(config.num_download_workers)
        ]

        self._merge_pool: list[MergeWorker] = [
            MergeWorker(
                worker_id=f"merge_worker_{index}",
                input_queue=queues.merge,
                output_queue=queues.upload if google_drive_token else None,
                notification_queue=queues.notification,
                config=WorkerConfig(),
                multi_format_exporter=MultiFormatExporter(),
            )
            for index in range(config.num_merge_workers)
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
                    input_queue=queues.upload,
                    output_queue=None,
                    notification_queue=queues.notification,
                    config=WorkerConfig(),
                    google_drive_archive_store=GoogleDriveArchiveStore(
                        google_drive_token, folder_cache=google_drive_folder_cache
                    ),
                )
                for index in range(config.num_upload_workers)
            ]

        self._notification_worker = NotificationWorker(
            worker_id="notification_worker",
            input_queue=queues.notification,
            on_status_update=on_status_update,
            benchmark=BenchmarkManager() if config.benchmark_enabled else None,
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

    def get_benchmark_aggregates(self) -> BenchmarkAggregates | None:
        """Return benchmark aggregates from the notification worker."""
        return self._notification_worker.get_benchmark_aggregates()

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
