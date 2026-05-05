import logging
from copy import deepcopy
from typing import TYPE_CHECKING

from textual import on, work
from textual.app import App
from textual.reactive import reactive

from .integrations.content_providers import ContentProviderManager
from .models.app_config import AppConfig
from .pipeline import PipelineManager
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
from .utils.benchmark_report import write_benchmark_report
from .utils.settings_manager import save_settings
from .workers.jobs import FetchingResourcesJob

if TYPE_CHECKING:
    from .screens.selection_screen import PartialJob

logger = logging.getLogger(__name__)


class MangaArchiverApp(App):
    """The core Textual application class for top level event handling.

    Attributes:
        _pipeline_manager (PipelineManager): The pipeline manager instance
        _favorite_repository (FavoriteRepository): The favorite repository
        _provider_manager (ContentProviderManager): The content provider manager
        _backlog (list[FetchingResourcesJob] | None): The backlog of missing chapters
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
        pipeline_manager: PipelineManager,
        app_config: AppConfig,
        favorite_repository: FavoriteRepository,
        provider_manager: ContentProviderManager,
        backlog: list[FetchingResourcesJob] | None = None,
        **kwargs,
    ) -> None:
        """Initialize the MangaArchiverApp.

        Args:
            pipeline_manager: Un-started pipeline manager for the app lifecycle
            app_config: The application configuration
            favorite_repository: The favorite repository
            backlog: Pre-fetched jobs to enqueue when pipeline starts
            provider_manager: Content provider manager (injected)
        """
        super().__init__(**kwargs)

        self._pipeline_manager = pipeline_manager
        self._app_config = app_config
        self._backlog = backlog

        self._favorite_repository = favorite_repository
        self._provider_manager = provider_manager
        self._favorites = []

        self.mutate_reactive(MangaArchiverApp._app_config)

    async def _load_favorites(self) -> None:
        """Load favorites from the database."""
        try:
            self._favorites = await self._favorite_repository.get_all()
            self.mutate_reactive(MangaArchiverApp._favorites)
        except Exception as e:
            logger.error("Failed to load favorites from database: %s", e)
            self.notify("Failed to load favorites from database", severity="error")
            self._favorites = []

        self.mutate_reactive(MangaArchiverApp._favorites)

    @work
    async def _setup_pipeline_manager(self) -> None:
        """Start the pipeline manager and process backlog jobs."""
        if self._backlog:
            self.notify(
                f"Enqueueing {len(self._backlog)} jobs from backlog, this may take a while...",
                severity="information",
            )

        await self._pipeline_manager.start(self._backlog)

    @work
    @on(SelectionScreen.EnqueueJobs)
    async def _enqueue_jobs(self, event: SelectionScreen.EnqueueJobs) -> None:
        """Enqueue jobs to the pipeline manager."""
        partial_jobs: list[PartialJob] = event.partial_jobs
        jobs: list[FetchingResourcesJob] = [
            FetchingResourcesJob(
                id=partial_job["chapter_id"],
                manga_title=partial_job["manga_title"],
                chapter_id=partial_job["chapter_id"],
                chapter_number=partial_job["chapter_number"],
                chapter_title=partial_job["chapter_title"],
                app_config=deepcopy(self._app_config),
                source=partial_job["source"],
            )
            for partial_job in partial_jobs
        ]

        await self._pipeline_manager.enqueue_jobs(jobs)

    async def on_mount(self) -> None:
        """On mount, install screens and start pipeline manager."""
        await self._load_favorites()

        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(self._provider_manager), name="search_screen")
        self.install_screen(
            SettingsScreen().data_bind(app_config=MangaArchiverApp._app_config),
            name="settings_screen",
        )
        self.install_screen(
            DownloadsScreen(
                get_jobs=self._pipeline_manager.get_jobs,
                retry_failed_jobs=self._pipeline_manager.retry_failed_jobs,
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

        try:
            self._pipeline_manager.stop()
            write_benchmark_report(self._pipeline_manager.get_benchmark_results())
        except Exception as e:
            logger.error("Error during shutdown: %s", e)
        finally:
            self.exit()

    def action_safe_pop_screen(self) -> None:
        """Check current screen safely before popping."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            incomplete_count = self._pipeline_manager.incomplete_job_count()
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
    async def _on_favorite_deleted(self, event: FavoritesScreen.Deleted) -> None:
        """Delete a favorite manga from the database then update in-memory copy."""
        manga_id, manga_title = (
            event.deleted_manga.id,
            event.deleted_manga.title,
        )

        try:
            await self._favorite_repository.delete_by_id(manga_id)
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
    async def _on_favorite_added(self, event: SearchScreen.FavoriteAdded) -> None:
        """Add a favorite manga to the database then update in-memory copy."""
        favorite_manga: FavoriteManga = event.favorited_manga

        try:
            was_created = await self._favorite_repository.create_one(favorite_manga)
        except Exception as e:
            logger.error("Failed to add %s to favorites: %s", favorite_manga.title, e)
            self.notify("Failed to add favorite", severity="error")
            return

        if not was_created:
            return

        self._favorites.append(favorite_manga)
        self.mutate_reactive(MangaArchiverApp._favorites)
        self.notify(
            f"Added '{favorite_manga.title}' to favorites",
            severity="information",
        )
