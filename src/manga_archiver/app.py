import logging
from pathlib import Path
from typing import TYPE_CHECKING

import aiohttp
from textual import on, work
from textual.app import App
from textual.reactive import reactive

from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .models.app_config import AppConfig
from .pipeline_manager import PipelineConfig, PipelineManager
from .repositories import FavoriteRepository
from .repositories.types import FavoriteManga
from .screens import (
    DownloadsScreen,
    FavoritesScreen,
    MenuScreen,
    QuitScreen,
    SearchScreen,
    SelectionScreen,
    SettingsScreen,
)
from .utils import DownloadClient
from .utils.settings_manager import save_settings
from .workers.jobs import FetchingResourcesJob

if TYPE_CHECKING:
    from .screens.selection_screen import PartialJob

import asyncio

from .constants.defaults import (
    DEFAULT_AUTO_EXIT_CONFIRM_COUNT,
    DEFAULT_AUTO_EXIT_POLL_INTERVAL,
)

logger = logging.getLogger(__name__)


class MangaArchiverApp(App):
    """The core Textual application class for top level event handling.

    Attributes:
        _pipeline_config (PipelineConfig): The pipeline configuration
        _pipeline_manager (PipelineManager | None): The pipeline manager instance
        _favorite_repository (FavoriteRepository): The favorite repository
        _google_drive_client (GoogleDriveClient | None): The Google Drive client
        _session (aiohttp.ClientSession): The aiohttp session
        _provider_manager (ContentProviderManager): The content provider manager
        _download_client (DownloadClient): The download client
        _backlog (list[FetchingResourcesJob] | None): The backlog of missing chapters
        _auto_exit (bool): Whether to automatically exit when all jobs are complete

    Reactive Attributes:
        _app_config (AppConfig): The application configuration
        _favorites (list[FavoriteManga]): List of favorited manga with manga_id and manga_title
    """

    DEFAULT_CSS = """
        MangaArchiverApp {
            height: 100%;
            width: 100%;
        }
    """

    BINDINGS = [("escape", "safe_pop_screen", "Go back")]

    _app_config: reactive[AppConfig] = reactive(AppConfig)
    _favorites: reactive[list[FavoriteManga]] = reactive([])

    def __init__(
        self,
        pipeline_config: PipelineConfig,
        app_config: AppConfig,
        favorite_repository: FavoriteRepository,
        google_drive_client: GoogleDriveClient | None,
        backlog: list[FetchingResourcesJob] | None = None,
        auto_exit: bool = False,
        **kwargs,
    ) -> None:
        """Initialize the MangaArchiverApp.

        Args:
            pipeline_config: The pipeline configuration
            app_config: The application configuration
            favorite_repository: The favorite repository
            google_drive_client: The Google Drive client
            backlog: Pre-fetched jobs to enqueue when pipeline starts
            auto_exit: Whether to automatically exit the application
        """
        super().__init__(**kwargs)

        self._pipeline_config = pipeline_config
        self._app_config = app_config
        self._backlog = backlog
        self._auto_exit = auto_exit

        self._pipeline_manager: PipelineManager | None = None
        self._favorite_repository = favorite_repository
        self._google_drive_client = google_drive_client

        try:
            self._favorites = self._favorite_repository.get_all()
        except Exception as e:
            logger.error("Failed to load favorites from database: %s", e)
            self.notify("Failed to load favorites from database", severity="error")
            self._favorites = []

        self.mutate_reactive(MangaArchiverApp._app_config)
        self.mutate_reactive(MangaArchiverApp._favorites)

    @work
    async def _poll_pipeline_manager_is_done(self) -> None:
        """Poll pipeline manager until all jobs are done."""
        confirm_count = 0

        while True:
            await asyncio.sleep(DEFAULT_AUTO_EXIT_POLL_INTERVAL)

            if not self._pipeline_manager:
                continue

            if self._pipeline_manager.is_done():
                self.notify(
                    f"auto exit confirm count: {confirm_count + 1}",
                    severity="information",
                )
                confirm_count += 1

            if confirm_count >= DEFAULT_AUTO_EXIT_CONFIRM_COUNT:
                break

        await self._on_quit(True)

    @work
    async def _setup_pipeline_manager(self) -> None:
        """Set up the pipeline manager, process backlog, and start it."""
        self._pipeline_manager = PipelineManager(
            self._provider_manager,
            self._download_client,
            self._pipeline_config,
            google_drive_client=self._google_drive_client,
        )

        if self._backlog:
            self.notify(
                f"Enqueueing {len(self._backlog)} jobs from backlog, this may take a while...",
                severity="information",
            )

        if self._auto_exit:
            self._poll_pipeline_manager_is_done()

        await self._pipeline_manager.start(self._backlog)

    @work
    @on(SelectionScreen.EnqueueJobs)
    async def _enqueue_jobs(self, event: SelectionScreen.EnqueueJobs) -> None:
        """Enqueue jobs to the pipeline manager."""
        if not self._pipeline_manager:
            logger.error("Pipeline manager not initialized - missing from app setup")
            self.notify("Pipeline manager not initialized", severity="error")
            return

        partial_jobs: list[PartialJob] = event.partial_jobs
        jobs: list[FetchingResourcesJob] = [
            FetchingResourcesJob(
                id=partial_job["chapter_id"],
                manga_title=partial_job["manga_title"],
                chapter_id=partial_job["chapter_id"],
                chapter_number=partial_job["chapter_number"],
                chapter_title=partial_job["chapter_title"],
                output_directory=self._app_config.output_path,
                output_format=self._app_config.output_format,
                source=partial_job["source"],
            )
            for partial_job in partial_jobs
        ]

        await self._pipeline_manager.enqueue_jobs(jobs)

    async def on_mount(self) -> None:
        """On mount, initialize api and download clients before injecting into screens."""
        # This config is necessary to handle aiohttp auto use of aiodns, without it we get 443 errors
        self._session = aiohttp.ClientSession(
            connector=aiohttp.TCPConnector(resolver=aiohttp.resolver.ThreadedResolver())
        )
        self._provider_manager = ContentProviderManager(self._session)
        self._download_client = DownloadClient(self._session)

        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(self._provider_manager), name="search_screen")
        self.install_screen(
            SettingsScreen().data_bind(app_config=MangaArchiverApp._app_config),
            name="settings_screen",
        )
        self.install_screen(
            DownloadsScreen(
                # Lambda captures self by reference; null guard handles the window
                # between screen install and pipeline initialization
                lambda: self._pipeline_manager.get_jobs() if self._pipeline_manager else {}
            ),
            name="downloads_screen",
        )
        self.install_screen(
            FavoritesScreen().data_bind(favorites=MangaArchiverApp._favorites),
            name="favorites_screen",
        )

        self._setup_pipeline_manager()
        self.push_screen("menu_screen")

    async def _on_quit(self, confirmed: bool | None = False) -> None:
        """Stop all resources and exit the application."""
        if not confirmed:
            return

        if self._pipeline_manager:
            self._pipeline_manager.stop()

        if self._session:
            await self._session.close()

        benchmark_results = None

        if self._pipeline_manager and self._pipeline_config.benchmark_enabled:
            benchmark_results = self._pipeline_manager.get_benchmark_results()

        if benchmark_results:
            try:
                benchmark_dir = Path("~/.manga-archiver/benchmark").expanduser()
                benchmark_dir.mkdir(parents=True, exist_ok=True)
                metrics_file = benchmark_dir / "metrics.txt"

                with open(metrics_file, "w") as f:
                    f.write("Benchmark Results\n")
                    f.write("=" * 40 + "\n")
                    for key, value in benchmark_results.items():
                        if "ms" in key:
                            f.write(f"{key}: {value:.2f} ms\n")
                        elif "memory" in key:
                            f.write(f"{key}: {value:.2f} MB\n")
                        else:
                            f.write(f"{key}: {value}\n")
            except Exception as e:
                logger.error("Failed to write benchmark file: %s", e)

            logger.info("Aggregate Benchmark Results:")
            for aggregate in benchmark_results:
                logger.info("[%s]: %s", aggregate, benchmark_results[aggregate])

        self.exit()

    def action_safe_pop_screen(self) -> None:
        """Check current screen safely before popping."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            incomplete_count = (
                self._pipeline_manager.incomplete_job_count() if self._pipeline_manager else 0
            )
            self.push_screen(
                QuitScreen(incomplete_count),
                lambda confirmed: self._on_quit(confirmed),
            )
            return

        self.pop_screen()

    @on(SettingsScreen.Save)
    def _on_schedule_settings_save(self, event: SettingsScreen.Save) -> None:
        """Save settings to settings.json."""
        try:
            new_settings: AppConfig = event.app_config
            save_settings(new_settings)

            self._app_config = new_settings
            self.notify("Settings saved", severity="information")
        except ValueError:
            self.notify("Failed to save settings", severity="error")

    @on(FavoritesScreen.Deleted)
    def _on_favorite_deleted(self, event: FavoritesScreen.Deleted) -> None:
        """Delete a favorite manga from the database then update in-memory copy."""
        manga_id, manga_title = (
            event.deleted_manga.id,
            event.deleted_manga.title,
        )

        try:
            self._favorite_repository.delete_by_id(manga_id)
        except Exception as e:
            logger.error("Failed to remove %s from favorites: %s", manga_title, e)
            self.notify("Failed to remove favorite", severity="error")
            return

        self._favorites = [f for f in self._favorites if f.id != manga_id]
        self.mutate_reactive(MangaArchiverApp._favorites)
        self.notify(f"Removed '{manga_title}' from favorites", severity="information")

    @on(FavoritesScreen.Selected)
    def _on_favorite_selected(self, event: FavoritesScreen.Selected) -> None:
        """Navigate to the selection screen with the selected manga."""
        manga_id = event.selected_manga.id
        manga_title = event.selected_manga.title
        source = event.selected_manga.source

        self.push_screen(SelectionScreen(manga_id, manga_title, self._provider_manager, source))

    @on(SearchScreen.FavoriteAdded)
    def _on_favorite_added(self, event: SearchScreen.FavoriteAdded) -> None:
        """Add a favorite manga to the database then update in-memory copy."""
        favorite_manga: FavoriteManga = event.favorited_manga

        try:
            self._favorite_repository.create_one(favorite_manga)
        except Exception as e:
            logger.error("Failed to add %s to favorites: %s", favorite_manga.title, e)
            self.notify("Failed to add favorite", severity="error")
            return

        self._favorites.append(favorite_manga)
        self.mutate_reactive(MangaArchiverApp._favorites)
        self.notify(
            f"Added '{favorite_manga.title}' to favorites",
            severity="information",
        )
