import logging
from dataclasses import dataclass

from .integrations.content_providers import ContentProviderManager
from .integrations.storage_providers.google_drive import GoogleDriveArchiveStore
from .integrations.storage_providers.google_drive.types import ArchivedChapterScanResult
from .models import Chapter, ContentSource
from .models.app_config import AppConfig
from .repositories import FavoriteRepository
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class Manga:
    """Immutable data container representing a manga with chapters."""

    manga_title: str
    source: ContentSource
    api_chapters: list[Chapter]
    google_drive_chapters: list[float]


class BacklogSync:
    """Handles backlog sync of favorites with Google Drive."""

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        google_drive_archive_store: GoogleDriveArchiveStore,
        provider_manager: ContentProviderManager,
        app_config: AppConfig,
    ) -> None:
        """Initialize backlog sync.

        Args:
            favorite_repository: Repository for favorites
            google_drive_archive_store: Google Drive archive store (must be initialized)
            provider_manager: Content provider manager
            app_config: Application settings to pass through queued jobs
        """
        self._favorite_repository = favorite_repository
        self._google_drive_archive_store = google_drive_archive_store
        self._provider_manager = provider_manager
        self._app_config = app_config
        self._mangas: list[Manga] = []

    async def run(self) -> list[FetchingResourcesJob]:
        """Run the backlog sync process.

        Returns:
            list[FetchingResourcesJob]: Jobs to enqueue (missing chapters)
        """
        print("=== Backlog Sync ===")

        favorites = await self._favorite_repository.get_all()
        print(f"Found {len(favorites)} favorites")

        if not favorites:
            print("No favorites to sync")
            return []

        for favorite in favorites:
            manga_id = favorite.id
            manga_title = favorite.title
            source = favorite.source

            print(f"Fetching chapters for '{manga_title}'...")

            api_chapters = await self._fetch_api_chapters(
                self._provider_manager, source, manga_id, manga_title
            )
            if api_chapters is None:
                continue

            archived_chapters = await self._fetch_google_drive_chapters(manga_title, source.value)
            google_drive_chapters = archived_chapters.chapter_numbers

            status_message = (
                f"  {manga_title}: {len(api_chapters)} from API, "
                f"{len(google_drive_chapters)} in Google Drive"
            )
            if archived_chapters.skipped_file_count > 0:
                status_message += (
                    f", {archived_chapters.skipped_file_count} skipped due to "
                    "missing/invalid metadata"
                )
            print(status_message)

            self._mangas.append(
                Manga(
                    manga_title=manga_title,
                    source=source,
                    api_chapters=api_chapters,
                    google_drive_chapters=google_drive_chapters,
                )
            )

        print(f"\nScanned {len(self._mangas)} manga")

        return self._create_jobs()

    def _calculate_diff(self) -> list[tuple[str, ContentSource, Chapter]]:
        """Calculate missing chapters by comparing API chapters vs Google Drive.

        Returns:
            list[tuple[str, ContentSource, Chapter]]: List of tuples containing
                (manga_title, source, chapter) for chapters missing in Google Drive
        """
        missing_chapters: list[tuple[str, ContentSource, Chapter]] = []

        for manga in self._mangas:
            google_drive_set = set(manga.google_drive_chapters)

            for chapter in manga.api_chapters:
                chapter_number = chapter.chapter_num
                if not isinstance(chapter_number, float):
                    logger.error("Skipping chapter %s - chapter number is not a float", chapter.id)
                    continue

                if chapter_number not in google_drive_set:
                    missing_chapters.append((manga.manga_title, manga.source, chapter))

        return missing_chapters

    def _create_jobs(self) -> list[FetchingResourcesJob]:
        """Create FetchingResourcesJob for missing chapters.

        Returns:
            list[FetchingResourcesJob]: List of jobs to enqueue
        """
        missing_chapters = self._calculate_diff()
        jobs = [
            FetchingResourcesJob(
                id=chapter.id,
                manga_title=manga_title,
                chapter_id=chapter.id,
                chapter_number=chapter.chapter_num,
                chapter_title=chapter.title,
                app_config=self._app_config,
                source=source,
            )
            for manga_title, source, chapter in missing_chapters
        ]

        print(f"Found {len(jobs)} missing chapters")
        return jobs

    async def _fetch_api_chapters(
        self,
        provider_manager: ContentProviderManager,
        source: ContentSource,
        manga_id: str,
        manga_title: str,
    ) -> list[Chapter] | None:
        """Fetch chapters from a content provider.

        Args:
            provider_manager: Content provider manager
            source: The content source
            manga_id: The manga ID
            manga_title: The manga title (for logging)

        Returns:
            list[Chapter] | None: List of chapters, or None if fetch failed
        """
        try:
            return await provider_manager.get_chapters(source, manga_id)
        except Exception as e:
            logger.error("Failed to get chapters for %s: %s", manga_title, e)
            print(f"ERROR: Failed to get chapters for '{manga_title}'")
            return None

    async def _fetch_google_drive_chapters(
        self, manga_title: str, source: str
    ) -> ArchivedChapterScanResult:
        """Fetch chapter numbers from Google Drive folder.

        Args:
            manga_title: The manga title to look up in folder cache
            source: The content source (e.g., "mangadex")

        Returns:
            ArchivedChapterScanResult: Chapter numbers found in Google Drive and skipped file count.
        """
        return await self._google_drive_archive_store.scan_archived_chapters(manga_title, source)
