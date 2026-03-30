from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App

from .integrations import MangaDexApiClient
from .screens import MenuScreen, SearchScreen, SelectionScreen, SettingsScreen
from .utils import DownloadClient, SessionManager
from .workers import PipelineConfig, PipelineManager

if TYPE_CHECKING:
    from .screens.selection_screen import PartialJob

from pathlib import Path

from .models import OutputFormat
from .workers.jobs import FetchingResourcesJob


class MangaDexDownloaderApp(App):
    """
    The core Textual application class for top level event handling.

    Attributes:
        pipeline_manager (PipelineManager | None): The pipeline manager instance
    """

    DEFAULT_CSS = """
        MangaDexDownloaderApp {
            height: 100%;
            width: 100%;
        }
    """

    BINDINGS = [("escape", "safe_pop_screen", "Go back")]

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._pipeline_manager: PipelineManager | None = None

    @work
    async def _setup_pipeline_manager(self) -> None:
        self._session_manager = SessionManager().create_session()
        self._mangadex_client = MangaDexApiClient(self._session_manager)
        self._download_client = DownloadClient(self._session_manager)

        self._pipeline_manager = PipelineManager(
            self._mangadex_client,
            self._download_client,
            lambda *args: None,
            PipelineConfig(
                num_resolve_workers=5,
                num_download_workers=5,
                num_merge_workers=5,
                resolve_rate_limit=5,
                download_rate_limit=5,
                benchmark_enabled=True,
                benchmark_expected_count=30,
            ),
        )

        await self._pipeline_manager.start()

    @work
    @on(SelectionScreen.EnqueueJobs)
    async def _enqueue_jobs(self, event: SelectionScreen.EnqueueJobs) -> None:
        if not self._pipeline_manager:
            self.notify("Pipeline manager not initialized", severity="error")
            self.log.error("Pipeline manager not initialized")
            return

        partial_jobs: list[PartialJob] = event.partial_jobs
        jobs: list[FetchingResourcesJob] = [
            FetchingResourcesJob(
                id=partial_job["chapter_id"],
                manga_title=partial_job["manga_title"],
                chapter_id=partial_job["chapter_id"],
                chapter_title=partial_job["chapter_title"],
                output_directory=Path("C:\\Users\\JFang\\Desktop\\trash"),
                output_format=OutputFormat.PDF,
                start_time=-1,
                end_time=-1,
            )
            for partial_job in partial_jobs
        ]

        await self._pipeline_manager.enqueue_jobs(jobs)

    def on_mount(self) -> None:
        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(), name="search_screen")
        self.install_screen(SettingsScreen(), name="settings_screen")

        self._setup_pipeline_manager()
        self.push_screen("menu_screen")

    def action_safe_pop_screen(self) -> None:
        """A safe version of pop_screen that checks if the current screen is a MenuScreen before popping."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            return

        self.pop_screen()
