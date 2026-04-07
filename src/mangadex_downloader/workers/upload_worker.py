import logging
import time
from asyncio import Queue

from ..enums import JobStatus
from ..integrations.storage_providers.google_drive import GoogleDriveClient
from .base import Worker, WorkerConfig
from .jobs import Job, NotificationJob, UploadJob

logger = logging.getLogger(__name__)


class UploadWorker(Worker):
    """Worker for uploading merged files to cloud storage."""

    def __init__(
        self,
        id: str,  # noqa: A002
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        google_drive_client: GoogleDriveClient,
    ):
        """Initialize the upload worker.

        Args:
            id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            google_drive_client: The Google Drive client for uploads
        """
        super().__init__(id, input_queue, output_queue, config, notification_queue)

        self._google_drive_client = google_drive_client

    async def _do_work(self, job: UploadJob) -> None:
        """Upload the merged file to Google Drive.

        Args:
            job: The upload job containing file data to upload
        """
        (
            job_id,
            manga_title,
            _,
            _,
            output_format,
            complete_file_data,
            full_name,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.output_directory,
            job.output_format,
            job.complete_file_data,
            job.full_name,
        )

        upload_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.UPLOADING, upload_start)

        try:
            folder_id = await self._google_drive_client.get_or_create_manga_folder(manga_title)

            uploaded_id = await self._google_drive_client.upload_file(
                file_data=complete_file_data,
                file_name=full_name,
                folder_id=folder_id,
                mimetype=output_format.mime_type,
            )

            upload_end = time.perf_counter_ns()

            if uploaded_id:
                await self._send_notification(job, JobStatus.UPLOADING, upload_start, upload_end)

                return None
            else:
                logger.error("Failed to upload %s to Google Drive", full_name)
                await self._send_notification(job, JobStatus.FAILED)

        except Exception as e:
            logger.error("Upload error for %s: %s", job_id, e)
            raise
