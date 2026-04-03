from typing import TYPE_CHECKING

import aiohttp
from textual import on, work
from textual.app import App
from textual.reactive import reactive

from .db import init_db
from .integrations import MangaDexApiClient
from .integrations.google_drive import GoogleDriveClient
from .models import AppConfig
from .repositories import FavoriteRepository
from .screens import (
    DownloadsScreen,
    FavoritesScreen,
    MenuScreen,
    QuitScreen,
    SearchScreen,
    SelectionScreen,
    SettingsScreen,
)
from .utils import DownloadClient, save_settings
from .workers import PipelineConfig, PipelineManager
from .workers.jobs import FetchingResourcesJob

if TYPE_CHECKING:
    from .screens.selection_screen import PartialJob
    from .types import ProcessedManga


class MangaDexDownloaderApp(App):
    """
    The core Textual application class for top level event handling.

    Attributes:
        pipeline_manager (PipelineManager | None): The pipeline manager instance
        favorites: List of favorited manga with manga_id and manga_title
    """

    DEFAULT_CSS = """
        MangaDexDownloaderApp {
            height: 100%;
            width: 100%;
        }
    """

    BINDINGS = [("escape", "safe_pop_screen", "Go back")]

    _app_config: reactive[AppConfig] = reactive(AppConfig)
    favorites: reactive[list[dict[str, str]]] = reactive([])

    def __init__(
        self,
        pipeline_config: PipelineConfig,
        app_config: AppConfig,
        favorite_repository: FavoriteRepository,
        google_drive_client: GoogleDriveClient | None = None,
        **kwargs,
    ) -> None:
        super().__init__(**kwargs)

        self._pipeline_config = pipeline_config
        self._app_config = app_config
        self._pipeline_manager: PipelineManager | None = None
        self._favorite_repository = favorite_repository
        self._google_drive_client = google_drive_client

        init_db()
        try:
            self.favorites = self._favorite_repository.get_all()
        except Exception:
            self.notify("Failed to load favorites from database", severity="error")
            self.favorites = []

        self.mutate_reactive(MangaDexDownloaderApp._app_config)
        self.mutate_reactive(MangaDexDownloaderApp.favorites)

    @work
    async def _setup_pipeline_manager(self) -> None:
        self._pipeline_manager = PipelineManager(
            self._mangadex_client,
            self._download_client,
            self._pipeline_config,
            google_drive_client=self._google_drive_client,
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

    async def on_mount(self) -> None:
        self._session = aiohttp.ClientSession()
        self._mangadex_client = MangaDexApiClient(self._session)
        self._download_client = DownloadClient(self._session)

        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(self._mangadex_client), name="search_screen")
        self.install_screen(
            SettingsScreen().data_bind(app_config=MangaDexDownloaderApp._app_config),
            name="settings_screen",
        )
        self.install_screen(
            DownloadsScreen(
                # Lambda captures self by reference; null guard handles the window
                # between screen install and pipeline initialization
                lambda: (
                    self._pipeline_manager.get_jobs() if self._pipeline_manager else {}
                )
            ),
            name="downloads_screen",
        )
        self.install_screen(
            FavoritesScreen().data_bind(favorites=MangaDexDownloaderApp.favorites),
            name="favorites_screen",
        )

        self._setup_pipeline_manager()
        self.push_screen("menu_screen")

    async def _on_quit(self, confirmed: bool | None = False) -> None:
        if not confirmed:
            return

        if self._pipeline_manager:
            self._pipeline_manager.stop()
        if self._session:
            await self._session.close()

        self.exit()

    def action_safe_pop_screen(self) -> None:
        """A safe version of pop_screen that checks if the current screen is a MenuScreen before popping."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            incomplete_count = (
                self._pipeline_manager.incomplete_job_count()
                if self._pipeline_manager
                else 0
            )
            self.push_screen(
                QuitScreen(incomplete_count),
                lambda confirmed: self._on_quit(confirmed),
            )
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
        except ValueError:
            self.notify("Failed to save settings", severity="error")

    @on(FavoritesScreen.Deleted)
    def _on_favorite_deleted(self, event: FavoritesScreen.Deleted) -> None:
        try:
            self._favorite_repository.delete_by_id(event.manga_id)
        except Exception:
            self.notify("Failed to remove favorite", severity="error")
            return

        self.favorites = [f for f in self.favorites if f["manga_id"] != event.manga_id]
        self.mutate_reactive(MangaDexDownloaderApp.favorites)
        self.notify(
            f"Removed '{event.manga_title}' from favorites", severity="information"
        )

    @on(FavoritesScreen.Selected)
    def _on_favorite_selected(self, event: FavoritesScreen.Selected) -> None:
        manga: ProcessedManga = {"id": event.manga_id, "title": event.manga_title}
        self.push_screen(SelectionScreen(manga, self._mangadex_client))

    @on(SearchScreen.FavoriteAdded)
    def _on_favorite_added(self, event: SearchScreen.FavoriteAdded) -> None:
        try:
            self._favorite_repository.create_one(event.manga_id, event.manga_title)
        except Exception:
            self.notify("Failed to add favorite", severity="error")
            return

        self.favorites.append(
            {"manga_id": event.manga_id, "manga_title": event.manga_title}
        )
        self.mutate_reactive(MangaDexDownloaderApp.favorites)
        self.notify(f"Added '{event.manga_title}' to favorites", severity="information")
