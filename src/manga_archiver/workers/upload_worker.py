from asyncio import Queue

from ..integrations.storage_providers.google_drive import GoogleDriveArchiveStore
from .base import Worker, WorkerConfig
from .jobs import Job, JobStatus, NotificationJob, UploadJob


class UploadWorker(Worker):
    """Worker for uploading merged files to cloud storage."""

    def __init__(
        self,
        worker_id: str,
        input_queue: Queue[Job],
        output_queue: Queue[Job] | None,
        notification_queue: Queue[NotificationJob],
        config: WorkerConfig,
        google_drive_archive_store: GoogleDriveArchiveStore,
    ) -> None:
        """Initialize the upload worker.

        Args:
            worker_id: The ID of the worker
            input_queue: The input queue for the worker
            output_queue: The output queue for the worker
            notification_queue: The queue for notification jobs
            config: The configuration for the worker
            google_drive_archive_store: The Google Drive archive store for uploads
        """
        super().__init__(
            worker_id, input_queue, output_queue, config, notification_queue, JobStatus.UPLOADING
        )

        self._google_drive_archive_store = google_drive_archive_store

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

        chapter_title = job.chapter_title if job.chapter_title else "untitled"
        chapter_num = f"{job.chapter_number:g}"

        uploaded_id = await self._google_drive_archive_store.upload_chapter(
            file_data=complete_file_data,
            file_name=full_name,
            manga_title=manga_title,
            source=job.source.value,
            chapter_num=chapter_num,
            chapter_title=chapter_title,
            mimetype=app_config.output_format.mime_type,
        )

        if not uploaded_id:
            raise RuntimeError(f"Failed to upload {full_name} to Google Drive")
