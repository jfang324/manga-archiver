import logging
import re
from dataclasses import dataclass
from pathlib import Path

from .integrations.storage_providers.google_drive import GoogleDriveClient
from .repositories import FavoriteRepository
from .types import ProcessedChapter
from .workers.jobs import FetchingResourcesJob

logger = logging.getLogger(__name__)


@dataclass
class MangaChapters:
    """Tracks chapters for a manga."""

    manga_id: str
    manga_title: str
    api_chapters: list[ProcessedChapter]
    gdrive_chapters: list[int]


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
        self._manga_chapters: list[MangaChapters] = []

    def run(self) -> list[FetchingResourcesJob]:
        """Run the headless sync process.

        Returns:
            list[FetchingResourcesJob]: Jobs to enqueue (missing chapters)
        """
        print("=== Headless Sync ===")

        favorites = self._favorite_repository.get_all()
        print(f"Found {len(favorites)} favorites")

        if not favorites:
            print("No favorites to sync")
            return []

        for favorite in favorites:
            manga_title = favorite["manga_title"]

            gdrive_folder_id = self._google_drive_client._folder_cache.get(manga_title)
            if gdrive_folder_id:
                files = self._google_drive_client.get_files_in_folder(gdrive_folder_id)
                gdrive_chapters = self._parse_chapter_numbers(files)
            else:
                gdrive_chapters = []

            print(f"  {manga_title}: {len(gdrive_chapters)} chapters in Google Drive")

        print(f"\nScanned {len(self._manga_chapters)} manga in Google Drive")

        return []

    def _parse_chapter_numbers(self, files: list[dict]) -> list[int]:
        """Parse chapter numbers from file names.

        Args:
            files: List of file dictionaries with 'name' key

        Returns:
            list[int]: List of parsed chapter numbers
        """
        chapter_numbers: list[int] = []

        for file in files:
            name = file.get("name", "")
            match = re.search(r"\[(\d+)\]", name)
            if match:
                chapter_numbers.append(int(match.group(1)))

        return chapter_numbers
