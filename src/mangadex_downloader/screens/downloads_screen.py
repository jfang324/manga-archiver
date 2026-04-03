from typing import Callable

from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..enums import JobStatus
from ..workers.jobs import JobMetadata

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
        """Setup polling for job status updates on mount."""
        table = self.query_one(DataTable)
        table.add_columns("Job ID", "Manga", "Chapter", "Download Time", "Status")

        self.set_interval(1, self._poll_jobs)

    def _poll_jobs(self) -> None:
        self.jobs = self._get_jobs()

    def watch_jobs(self) -> None:
        table = self.query_one(DataTable)
        table.clear()

        for job_id, (status, metadata) in self.jobs.items():
            if metadata.end_time == -1:
                download_time = "N/A"
            else:
                duration_s = (metadata.end_time - metadata.start_time) / 1_000_000_000
                download_time = f"{duration_s:.2f}s"

            table.add_row(
                job_id,
                metadata.manga_title,
                metadata.chapter_title,
                download_time,
                status.value,
            )
