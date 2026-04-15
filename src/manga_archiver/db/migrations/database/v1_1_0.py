"""Migration v1.1.0: Add source tracking to favorites.

This migration:
- Renames manga_id → id
- Renames manga_title → title
- Adds source column with default 'mangadex'
"""

import logging
from sqlite3 import Cursor

from manga_archiver.db.schema_manager import _version_compare

logger = logging.getLogger(__name__)

MIGRATION_VERSION = "v1.1.0"


def migrate(current_version: str, cursor: Cursor) -> str:
    """Execute database migration from pre-v1.1.0 to v1.1.0.

    Args:
        current_version: The current database version from schema_version table.
        cursor: Database cursor to use for operations.

    Returns:
        str: message describing changes made.
    """
    if _version_compare(MIGRATION_VERSION, current_version) <= 0:
        return f"Already at {MIGRATION_VERSION} - no migration needed"

    cursor.execute("PRAGMA table_info(favorite_manga)")
    columns = {row[1] for row in cursor.fetchall()}

    if "manga_id" in columns and "manga_title" in columns:
        cursor.execute("""
            CREATE TABLE favorite_manga_new (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                source TEXT NOT NULL DEFAULT 'mangadex'
            )
        """)

        cursor.execute("""
            INSERT INTO favorite_manga_new (id, title, source)
            SELECT manga_id, manga_title, 'mangadex' FROM favorite_manga
        """)

        cursor.execute("DROP TABLE favorite_manga")
        cursor.execute("ALTER TABLE favorite_manga_new RENAME TO favorite_manga")

    cursor.execute(
        "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
        (MIGRATION_VERSION, "database"),
    )

    return f"Migrated to {MIGRATION_VERSION}: Added source tracking to favorites"
