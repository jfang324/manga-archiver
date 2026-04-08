import logging
import re
from dataclasses import dataclass
from pathlib import Path

import aiohttp

from .enums import OutputFormat
from .integrations.content_providers import MangaDexApiClient
from .integrations.storage_providers.google_drive import GoogleDriveClient
from .repositories import FavoriteRepository
from .types import ProcessedChapter
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


@dataclass
class Manga:
    """Represents a manga with its chapters from API and Google Drive."""

    manga_title: str
    api_chapters: list[ProcessedChapter]
    google_drive_chapters: list[float]


class HeadlessSync:
    """Handles headless sync of favorites with Google Drive."""

    def __init__(
        self,
        favorite_repository: FavoriteRepository,
        google_drive_client: GoogleDriveClient,
        output_directory: Path,
        output_format: str,
    ) -> None:
        """Initialize headless sync.

        Args:
            favorite_repository: Repository for favorites
            google_drive_client: Google Drive client (must be initialized)
            output_directory: Where to save downloads
            output_format: Output format (pdf, cbz, epub)
        """
        self._favorite_repository = favorite_repository
        self._google_drive_client = google_drive_client
        self._output_directory = output_directory
        self._output_format = output_format
        self._mangas: list[Manga] = []

    async def run(self) -> list[FetchingResourcesJob]:
        """Run the headless sync process.

        Note: We create the aiohttp ClientSession here instead of passing it in
        because this method runs in its own event loop (via asyncio.run()) in main.py.
        The CLI entry point doesn't have an active event loop, so we can't create
        the session there - we create it here where we have an active loop.

        Returns:
            list[FetchingResourcesJob]: Jobs to enqueue (missing chapters)
        """
        print("=== Headless Sync ===")

        async with aiohttp.ClientSession() as session:
            mangadex_client = MangaDexApiClient(session)

            favorites = self._favorite_repository.get_all()
            print(f"Found {len(favorites)} favorites")

            if not favorites:
                print("No favorites to sync")
                return []

            for favorite in favorites:
                manga_id = favorite["manga_id"]
                manga_title = favorite["manga_title"]

                print(f"Fetching chapters for '{manga_title}'...")

                api_chapters = await self._fetch_api_chapters(
                    mangadex_client, manga_id, manga_title
                )
                if api_chapters is None:
                    continue

                google_drive_chapters = self._fetch_google_drive_chapters(manga_title)

                print(
                    f"  {manga_title}: {len(api_chapters)} from API, "
                    f"{len(google_drive_chapters)} in Google Drive"
                )

                self._mangas.append(
                    Manga(
                        manga_title=manga_title,
                        api_chapters=api_chapters,
                        google_drive_chapters=google_drive_chapters,
                    )
                )

            print(f"\nScanned {len(self._mangas)} manga")

        return self._create_jobs()

    def _calculate_diff(self) -> list[tuple[str, ProcessedChapter]]:
        """Calculate missing chapters by comparing API chapters vs Google Drive.

        Returns:
            list[tuple[str, ProcessedChapter]]: List of tuples containing (manga_title, chapter)
                for chapters missing in Google Drive
        """
        missing_chapters: list[tuple[str, ProcessedChapter]] = []

        for manga in self._mangas:
            google_drive_set = set(manga.google_drive_chapters)

            for chapter in manga.api_chapters:
                chapter_str = chapter.get("chapter")
                if not chapter_str:
                    logger.error("Skipping chapter %s - no chapter number", chapter.get("id"))
                    continue

                try:
                    chapter_num = float(chapter_str)
                except (ValueError, TypeError) as e:
                    logger.error(
                        "Failed to parse chapter number '%s' for %s: %s",
                        chapter_str,
                        chapter.get("id"),
                        e,
                    )
                    continue

                if chapter_num not in google_drive_set:
                    missing_chapters.append((manga.manga_title, chapter))

        return missing_chapters

    def _create_jobs(self) -> list[FetchingResourcesJob]:
        """Create FetchingResourcesJob for missing chapters.

        Returns:
            list[FetchingResourcesJob]: List of jobs to enqueue
        """
        missing_chapters = self._calculate_diff()

        jobs: list[FetchingResourcesJob] = []
        for manga_title, chapter in missing_chapters:
            chapter_number = chapter.get("chapter")
            chapter_title = chapter.get("title", "untitled")

            jobs.append(
                FetchingResourcesJob(
                    id=chapter["id"],
                    manga_title=manga_title,
                    chapter_id=chapter["id"],
                    chapter_number=chapter_number,
                    chapter_title=chapter_title,
                    output_directory=self._output_directory,
                    output_format=OutputFormat(self._output_format),
                )
            )

        return jobs

    async def _fetch_api_chapters(
        self,
        client: MangaDexApiClient,
        manga_id: str,
        manga_title: str,
    ) -> list[ProcessedChapter] | None:
        """Fetch chapters from MangaDex API.

        Args:
            client: MangaDex API client
            manga_id: The manga ID
            manga_title: The manga title (for logging)

        Returns:
            list[ProcessedChapter] | None: List of chapters, or None if fetch failed
        """
        try:
            return await client.get_chapters(manga_id)
        except Exception as e:
            logger.error("Failed to get chapters for %s: %s", manga_title, e)
            print(f"  ERROR: Failed to get chapters for '{manga_title}'")
            return None

    def _fetch_google_drive_chapters(self, manga_title: str) -> list[float]:
        """Fetch chapter numbers from Google Drive folder.

        Args:
            manga_title: The manga title to look up in folder cache

        Returns:
            list[float]: List of chapter numbers found in Google Drive
        """
        folder_id = self._google_drive_client._folder_cache.get(manga_title)
        if folder_id:
            files = self._google_drive_client.get_files_in_folder(folder_id)
            return self._parse_chapter_numbers(files)
        return []

    def _parse_chapter_numbers(self, files: list[dict]) -> list[float]:
        """Parse chapter numbers from file names.

        Args:
            files: List of file dictionaries with 'name' key

        Returns:
            list[float]: List of parsed chapter numbers
        """
        chapter_numbers: list[float] = []

        for file in files:
            name = file.get("name", "")
            match = re.search(r"\[(\d+\.?\d*)\]", name)
            if match:
                chapter_numbers.append(float(match.group(1)))

        return chapter_numbers
