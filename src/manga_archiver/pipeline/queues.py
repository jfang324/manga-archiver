from asyncio import Queue
from dataclasses import dataclass

from ..workers.jobs import Job, NotificationJob
from ..workers.scheduler import SchedulerFeedback


@dataclass(frozen=True)
class PipelineQueues:
    """The queue topology connecting the pipeline's worker stages.

    Attributes:
        resolve: Queue carrying FetchingResourcesJob into the resolve workers
        download: Queue carrying DownloadingJob into the download workers
        merge: Queue carrying MergingJob into the merge workers
        upload: Queue carrying UploadJob into the upload workers
        notification: Queue carrying NotificationJob into the notification worker
        resolve_scheduler_feedback: Optional feedback queue for the resolve scheduler
    """

    resolve: Queue[Job]
    download: Queue[Job]
    merge: Queue[Job]
    upload: Queue[Job]
    notification: Queue[NotificationJob]
    resolve_scheduler_feedback: Queue[SchedulerFeedback] | None = None
