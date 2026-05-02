import logging
import time
from asyncio import Queue

from ..integrations.storage_providers.google_drive import GoogleDriveClient
from ..integrations.storage_providers.google_drive.types import GoogleDriveFileMetadata
from .base import Worker, WorkerConfig
from .jobs import Job, JobStatus, NotificationJob, UploadJob

logger = logging.getLogger(__name__)


class UploadWorker(Worker):
    """Worker for uploading merged files to cloud storage."""

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        google_drive_client: GoogleDriveClient,
    ) -> None:
        """Initialize the upload worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            google_drive_client: The Google Drive client for uploads
        """
        super().__init__(worker_id, input_queue, output_queue, config, notification_queue)

        self._google_drive_client = google_drive_client

    async def _do_work(self, job: Job) -> None:
        """Upload the merged file to Google Drive.

        Args:
            job: The upload job containing file data to upload
        """
        if not isinstance(job, UploadJob):
            raise ValueError(f"Invalid job type: {type(job).__name__}")

        (
            job_id,
            manga_title,
            _,
            app_config,
            complete_file_data,
            full_name,
            _,
        ) = (
            job.id,
            job.manga_title,
            job.chapter_title,
            job.app_config,
            job.complete_file_data,
            job.full_name,
            job.source,
        )

        if not complete_file_data:
            raise ValueError(f"Job {job_id} complete_file_data is empty")

        if not isinstance(job.chapter_number, float):
            raise ValueError(f"Job {job_id} chapter_number must be a float")

        chapter_str = f"{job.chapter_number:g}"
        if chapter_str not in full_name:
            raise ValueError(
                f"Job {job_id} full_name '{full_name}' does not contain chapter_number '{job.chapter_number}'"
            )

        upload_start = time.perf_counter_ns()
        await self._send_notification(job, JobStatus.UPLOADING, upload_start)

        chapter_title = job.chapter_title if job.chapter_title else "untitled"
        chapter_num = f"{job.chapter_number:g}"

        try:
            folder_id = await self._google_drive_client.get_or_create_manga_folder(
                manga_title, source=job.source.value
            )

            file_metadata = GoogleDriveFileMetadata(
                source=job.source.value,
                chapter_num=chapter_num,
                chapter_title=chapter_title,
            )

            uploaded_id = await self._google_drive_client.upload_file(
                file_data=complete_file_data,
                file_name=full_name,
                folder_id=folder_id,
                mimetype=app_config.output_format.mime_type,
                file_metadata=file_metadata,
            )

            upload_end = time.perf_counter_ns()

            if uploaded_id:
                await self._send_notification(job, JobStatus.UPLOADING, upload_start, upload_end)
            else:
                logger.error("Failed to upload %s to Google Drive", full_name)
                await self._send_notification(job, JobStatus.FAILED)

        except Exception as e:
            logger.error("Upload error for %s: %s", job_id, e)
            raise
