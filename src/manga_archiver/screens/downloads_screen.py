from collections.abc import Awaitable, Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..workers.types import JobMetadata, JobStatus

JobStatusRecord = tuple[JobStatus, JobMetadata]


class DownloadsScreen(Screen):
    """Downloads screen showing real-time job status updates.

    Reactive Attributes:
        jobs (dict[str, JobStatusRecord]): Dictionary of job IDs to tuples of (status, metadata)
    """

    DEFAULT_CSS = """
    DownloadsScreen {
        height: 1fr;
    }

    DataTable {
        width: 100%;
        height: 100%;
    }
    """

    BINDINGS = [
        ("ctrl+r", "retry_failed", "Retry failed"),
    ]

    jobs: reactive[dict[str, JobStatusRecord]] = reactive({})

    def __init__(
        self,
        get_jobs: Callable[[], dict[str, JobStatusRecord]],
        retry_failed_jobs: Callable[[], Awaitable[int]] | None = None,
        **kwargs,
    ) -> None:
        """Initialize the DownloadsScreen.

        Args:
            get_jobs: Callable that returns the current job statuses
            retry_failed_jobs: Optional async callable to retry failed jobs
        """
        super().__init__(**kwargs)
        self._get_jobs = get_jobs
        self._retry_failed_jobs = retry_failed_jobs

    def compose(self) -> ComposeResult:
        yield DataTable(id="downloads_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        """Set up polling for job status updates on mount."""
        table = self.query_one(DataTable)
        table.add_columns(
            "Job ID", "Manga", "Chapter #", "Chapter Title", "Completed At", "Size (MB)", "Status"
        )

        self.set_interval(1, self._poll_jobs)

    def _poll_jobs(self) -> None:
        """Retrieve current job statuses and update class state."""
        self.jobs = self._get_jobs()

    def watch_jobs(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        for job_id, (status, metadata) in self.jobs.items():
            completed = "—"
            size_mb = f"{metadata.payload_size / (1024 * 1024):.2f}"

            if metadata.completed_at != -1:
                completed = datetime.fromtimestamp(metadata.completed_at).strftime("%H:%M:%S")

            table.add_row(
                job_id,
                metadata.manga_title,
                f"{metadata.chapter_number:g}",
                metadata.chapter_title,
                completed,
                size_mb,
                status.value,
            )

    async def action_retry_failed(self) -> None:
        """Retry all failed jobs."""
        if self._retry_failed_jobs is None:
            return

        count = await self._retry_failed_jobs()
        if count > 0:
            self.app.notify(f"Retrying {count} failed jobs")
        else:
            self.app.notify("No failed jobs to retry")
