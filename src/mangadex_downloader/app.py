from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App

from .integrations.mangadex import MangaDexApiClient
from .screens import MenuScreen, SearchScreen, SelectionScreen
from .utils.session_manager import SessionManager
from .workers import PipelineConfig, PipelineManager

if TYPE_CHECKING:
    from .workers.jobs import FetchingResourcesJob


class MangaDexDownloaderApp(App):
    """
    The core Textual application class for top level event handling.

    Attributes:

    Reactive Attributes:
    """

    DEFAULT_CSS = """
        MangaDexDownloaderApp {
            height: 100%;
            width: 100%;
        }
    """

    BINDINGS = [("escape", "safe_pop_screen", "Go back")]

    def __init__(self) -> None:
        super().__init__()

        self.pipeline_manager: PipelineManager | None = None

    @work
    async def _setup_pipeline(self) -> None:
        """Instantiate the pipeline manager and start it."""
        session_manager = SessionManager().create_session()
        mangadex_client = MangaDexApiClient(session_manager)

        self.pipeline_manager = PipelineManager(
            mangadex_client, lambda *args: None, PipelineConfig()
        )

        await self.pipeline_manager.start()

    @work
    @on(SelectionScreen.EnqueueJobs)
    async def _enqueue_jobs(self, event: SelectionScreen.EnqueueJobs) -> None:
        """Enqueue jobs to the resolve queue to start the pipeline."""
        if not self.pipeline_manager:
            self.notify("Pipeline manager not initialized", severity="error")
            self.log.error("Pipeline manager not initialized")
            return

        jobs: list[FetchingResourcesJob] = event.jobs

        await self.pipeline_manager.enqueue_jobs(jobs)

    def on_mount(self) -> None:
        """On mount, install all screens and push the menu screen to the screen stack."""
        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(), name="search_screen")

        self.push_screen("menu_screen")

        self._setup_pipeline()

    def action_safe_pop_screen(self) -> None:
        """Safely pop the screen."""

        # TODO: Remove this
        if not self.pipeline_manager:
            return
        self.notify(f"resolve_pipeline: {self.pipeline_manager.resolve_queue.qsize()}")
        self.notify(
            f"download_pipeline: {self.pipeline_manager.download_queue.qsize()}"
        )

        if isinstance(self.screen_stack[-1], MenuScreen):
            return

        self.pop_screen()
