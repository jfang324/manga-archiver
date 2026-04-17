from collections.abc import Callable
from datetime import datetime

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..workers.jobs import JobMetadata, JobStatus

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

    jobs: reactive[dict[str, JobStatusRecord]] = reactive({})

    def __init__(
        self,
        get_jobs: Callable[[], dict[str, JobStatusRecord]],
        **kwargs,
    ) -> None:
        """Initialize the DownloadsScreen.

        Args:
            get_jobs: Callable that returns the current job statuses
        """
        super().__init__(**kwargs)

        self._get_jobs = get_jobs

    def compose(self) -> ComposeResult:
        yield DataTable(id="downloads_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        """Set up polling for job status updates on mount."""
        table = self.query_one(DataTable)
        table.add_columns("Job ID", "Manga", "Chapter #", "Chapter Title", "Completed At", "Status")

        self.set_interval(1, self._poll_jobs)

    def _poll_jobs(self) -> None:
        self.jobs = self._get_jobs()

    def watch_jobs(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        for job_id, (status, metadata) in self.jobs.items():
            completed = "—"

            if metadata.completed_at != -1:
                completed = datetime.fromtimestamp(metadata.completed_at).strftime("%H:%M:%S")

            table.add_row(
                job_id,
                metadata.manga_title,
                f"{metadata.chapter_number:g}",
                metadata.chapter_title,
                completed,
                status.value,
            )
