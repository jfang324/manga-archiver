from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App
from textual.reactive import reactive

from .integrations import MangaDexApiClient
from .models import AppConfig
from .screens import (
    DownloadsScreen,
    FavoritesScreen,
    MenuScreen,
    SearchScreen,
    SelectionScreen,
    SettingsScreen,
)
from .utils import DownloadClient, SessionManager, save_settings
from .workers import PipelineConfig, PipelineManager
from .workers.jobs import FetchingResourcesJob

if TYPE_CHECKING:
    from .screens.selection_screen import PartialJob


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

    _app_config: reactive[AppConfig] = reactive(AppConfig)

    def __init__(
        self,
        pipeline_config: PipelineConfig,
        app_config: AppConfig,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._pipeline_config = pipeline_config
        self._app_config = app_config
        self._pipeline_manager: PipelineManager | None = None

        self.mutate_reactive(MangaDexDownloaderApp._app_config)

    @work
    async def _setup_pipeline_manager(self) -> None:
        self._session_manager = SessionManager().create_session()
        self._mangadex_client = MangaDexApiClient(self._session_manager)
        self._download_client = DownloadClient(self._session_manager)

        config = self._pipeline_config

        self._pipeline_manager = PipelineManager(
            self._mangadex_client,
            self._download_client,
            lambda *args: None,
            config,
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
                output_directory=self._app_config.output_path,
                output_format=self._app_config.output_format,
                start_time=-1,
                end_time=-1,
            )
            for partial_job in partial_jobs
        ]

        await self._pipeline_manager.enqueue_jobs(jobs)

    def on_mount(self) -> None:
        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(), name="search_screen")
        self.install_screen(
            SettingsScreen().data_bind(app_config=MangaDexDownloaderApp._app_config),
            name="settings_screen",
        )
        self.install_screen(DownloadsScreen(), name="downloads_screen")
        self.install_screen(FavoritesScreen(), name="favorites_screen")

        self._setup_pipeline_manager()
        self.push_screen("menu_screen")

    def action_safe_pop_screen(self) -> None:
        """A safe version of pop_screen that checks if the current screen is a MenuScreen before popping."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            return

        self.pop_screen()

    @on(SettingsScreen.ScheduleSettingsSave)
    def _on_schedule_settings_save(
        self, event: SettingsScreen.ScheduleSettingsSave
    ) -> None:
        try:
            new_settings: AppConfig = event.app_config
            save_settings(new_settings)
            self._app_config = new_settings
            self.notify("Settings saved", severity="information")
        except ValueError as e:
            self.log.error(f"Failed to save settings: {e}")
            self.notify(f"Failed to save: {e}", severity="error")
