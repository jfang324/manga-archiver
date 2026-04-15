"""Migration v1.1.0: Add source tracking to Google Drive folders.

This migration:
- Add source metadata to Google Drive folders with default 'mangadex'
"""

import logging
from sqlite3 import Cursor

from manga_archiver.db.schema_manager import _version_compare

logger = logging.getLogger(__name__)

MIGRATION_VERSION = "v1.1.0"


def migrate(current: str, cursor: Cursor) -> str:
    """Execute Google Drive migration from pre-v1.1.0 to v1.1.0.

    Args:
        current: The current database version from schema_version table.
        cursor: Database cursor to use for operations.

    Returns:
        str: message describing changes made.
    """
    if _version_compare(MIGRATION_VERSION, current) <= 0:
        return f"Already at or above {MIGRATION_VERSION} - no migration needed"

    cursor.execute(
        "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
        (MIGRATION_VERSION, "google_drive"),
    )
    return f"Migrated to {MIGRATION_VERSION}: Added source metadata to Google Drive folders"
