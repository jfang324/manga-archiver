"""Migration v1.1.0: Add source tracking to Google Drive folders and files.

This migration:
- Add source metadata to existing Google Drive folders with default 'mangadex'
- Add source, chapter_num, and chapter_title metadata to files
- Parse filenames to extract chapter info for legacy files
"""

import logging
import re
from pathlib import Path
from sqlite3 import Cursor

from manga_archiver.db.schema_manager import PreparedMigration, _version_compare
from manga_archiver.integrations.storage_providers.google_drive import GoogleDriveMigrationClient
from manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleDriveDirectory,
    GoogleDriveFileMetadata,
    GoogleDriveFolderMetadata,
)
from manga_archiver.utils.auth.google_drive import load_token

logger = logging.getLogger(__name__)

MIGRATION_VERSION = "v1.1.0"
DEFAULT_SOURCE = "mangadex"
DEFAULT_CHAPTER_NUM = "0"
DEFAULT_CHAPTER_TITLE = "untitled"


def _parse_filename(filename: str) -> tuple[str, str]:
    """Parse chapter number and title from filename.

    Pattern: "One Piece[1] - Romance Dawn.pdf"
    Returns: ("1", "Romance Dawn")

    Args:
        filename: The filename to parse

    Returns:
        tuple[str, str]: (chapter_num, chapter_title)
    """
    name = Path(filename).stem

    num_match = re.search(r"\[(\d+(?:\.\d+)?)\]", name)
    chapter_num = num_match.group(1) if num_match else DEFAULT_CHAPTER_NUM

    title_match = re.search(r"-\s*(.+)", name)
    chapter_title = title_match.group(1).strip() if title_match else DEFAULT_CHAPTER_TITLE

    return chapter_num, chapter_title


async def _count_items_needing_migration(
    client: GoogleDriveMigrationClient, sub_folders: list[GoogleDriveDirectory]
) -> tuple[int, int]:
    """Count folders and files that need metadata added.

    Args:
        client: The Google Drive client
        sub_folders: List of subfolders to check

    Returns:
        tuple[int, int]: (folders_needed, files_needed)
    """
    folders_needed = 0
    files_needed = 0

    for folder in sub_folders:  # type: ignore[attr-defined]
        app_props = folder.get("appProperties")
        if not app_props or not app_props.get("source"):
            folders_needed += 1

        files = await client.list_files(folder["id"])
        for f in files:
            file_props = f.get("appProperties")
            if not file_props or not file_props.get("source"):
                files_needed += 1

    return folders_needed, files_needed


async def _migrate_folder(
    client: GoogleDriveMigrationClient, folder: GoogleDriveDirectory, print_progress: bool = True
) -> tuple[int, int]:
    """Migrate a single folder and its files.

    Args:
        client: The Google Drive client
        folder: The folder dictionary
        print_progress: Whether to print progress messages

    Returns:
        tuple[int, int]: (migrated_folders, migrated_files)
    """
    folder_id = folder["id"]
    folder_name = folder["name"]
    app_props = folder.get("appProperties")

    migrated_folders = 0
    migrated_files = 0

    if app_props is None or "source" not in app_props:
        try:
            folder_metadata = GoogleDriveFolderMetadata(source=DEFAULT_SOURCE)
            await client.update_folder_metadata(folder_id, folder_metadata)
            migrated_folders += 1
        except Exception as e:
            logger.error("Failed to migrate folder %s: %s", folder_name, e)
            raise

    files = await client.list_files(folder_id)
    files_needing_migration = [f for f in files if not (f.get("appProperties") or {}).get("source")]

    for idx, file in enumerate(files_needing_migration, 1):
        file_id = file["id"]
        file_name = file["name"]
        file_props = file.get("appProperties")

        if file_props is None or "source" not in file_props:
            try:
                chapter_num, chapter_title = _parse_filename(file_name)

                file_metadata = GoogleDriveFileMetadata(
                    source=DEFAULT_SOURCE,
                    chapter_num=chapter_num,
                    chapter_title=chapter_title,
                )
                await client.update_file_metadata(file_id, file_metadata)
                migrated_files += 1

                if print_progress and idx % 10 == 0:
                    print(f"  {folder_name} - {idx}/{len(files_needing_migration)}")

            except Exception as e:
                logger.error("Failed to migrate file %s: %s", file_name, e)
                raise

    if print_progress and files:
        print(f"  Migrated {folder_name} ({len(files_needing_migration)} files)")

    return migrated_folders, migrated_files


async def _verify_migration(
    client: GoogleDriveMigrationClient, sub_folders: list[GoogleDriveDirectory]
) -> tuple[int, int]:
    """Verify migration was successful by re-counting items needing metadata.

    Args:
        client: The Google Drive client
        sub_folders: List of subfolders to check

    Returns:
        tuple[int, int]: (remaining_folders, remaining_files)
    """
    remaining_folders = 0
    remaining_files = 0

    for folder in sub_folders:  # type: ignore[attr-defined]
        app_props = folder.get("appProperties")
        if not app_props or not app_props.get("source"):
            remaining_folders += 1

        files = await client.list_files(folder["id"])
        for f in files:
            file_props = f.get("appProperties")
            if not file_props or not file_props.get("source"):
                remaining_files += 1

    return remaining_folders, remaining_files


def _prepare_version_record_message(message: str) -> PreparedMigration:
    def apply(cursor: Cursor) -> str:
        cursor.execute(
            "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
            (MIGRATION_VERSION, "google_drive"),
        )
        return message

    return PreparedMigration(apply=apply)


async def migrate(current: str, _cursor: Cursor) -> str | PreparedMigration:
    """Execute Google Drive migration from pre-v1.1.0 to v1.1.0.

    Args:
        current: The current database version from schema_version table.
        cursor: Database cursor to use for operations.

    Returns:
        str: message describing changes made.
    """
    if _version_compare(MIGRATION_VERSION, current) <= 0:
        return f"Already at or above {MIGRATION_VERSION} - no migration needed"

    token = load_token()
    if token is None:
        logger.error("No Google Drive token found, skipping file migration")
        return _prepare_version_record_message(
            f"Migrated to {MIGRATION_VERSION}: Skipped (no token)"
        )

    client = GoogleDriveMigrationClient(token)

    try:
        init_result = await client.initialize()
    except Exception as e:
        logger.error("Failed to initialize Google Drive client: %s", e)
        return _prepare_version_record_message(
            f"Migrated to {MIGRATION_VERSION}: Failed to initialize Drive client"
        )

    sub_folders = await client.list_child_folders(init_result.root_folder_id)

    # Pre-flight: count items needing migration
    total_folders_needed, total_files_needed = await _count_items_needing_migration(
        client, sub_folders
    )
    print(f"Found {total_folders_needed} folders and {total_files_needed} files to migrate")

    # Migrate all folders
    migrated_folders = 0
    migrated_files = 0

    for folder in sub_folders:
        folder_count, file_count = await _migrate_folder(client, folder)
        migrated_folders += folder_count
        migrated_files += file_count

    # Verification: re-count items needing migration
    refreshed_sub_folders = await client.list_child_folders(init_result.root_folder_id)
    remaining_folders, remaining_files = await _verify_migration(client, refreshed_sub_folders)
    print(
        f"Verification: {remaining_folders} folders, {remaining_files} files still need migration"
    )

    if remaining_folders == 0 and remaining_files == 0:
        print("Migration complete - all metadata added successfully")

    return _prepare_version_record_message(
        f"Migrated to {MIGRATION_VERSION}: {migrated_folders} folders, {migrated_files} files"
    )
