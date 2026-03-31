from textual.app import ComposeResult
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import DataTable, Footer

from ..enums import JobStatus
from ..workers.jobs import JobMetadata


class DownloadsScreen(Screen):
    """Downloads screen showing real-time job status updates."""

    DEFAULT_CSS = """
    DownloadsScreen {
        height: 1fr;
    }

    DataTable {
        width: 100%;
        height: 100%;
    }
    """

    jobs: reactive[dict[str, tuple[JobStatus, JobMetadata]]] = reactive({})

    def compose(self) -> ComposeResult:
        yield DataTable(id="downloads_table", cursor_type="row")
        yield Footer()

    def on_mount(self) -> None:
        table = self.query_one(DataTable)
        table.add_columns("Job ID", "Manga", "Chapter", "Download Time", "Status")
        self.set_interval(1, self._poll_jobs)

    def _poll_jobs(self) -> None:
        # direct access is required as pipeline_manager cannot be a reactive and thus can't be data-bound
        pipeline_manager = self.app._pipeline_manager  # type: ignore[attr-defined]
        if not pipeline_manager:
            return

        jobs = pipeline_manager.get_jobs()
        self.jobs = jobs

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
