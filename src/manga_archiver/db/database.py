import os
from pathlib import Path
from sqlite3 import Connection, connect

from .migrations import DEFAULT_DATABASE_VERSION, LEGACY_VERSION


def init_schema_version_table(conn: Connection) -> None:
    """Initialize schema_version table with appropriate starting version."""
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            system TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(version, system)
        )
    """)

    cursor.execute("""
        SELECT name FROM sqlite_master
        WHERE type='table' AND name='favorite_manga'
    """)
    table_exists = cursor.fetchone() is not None
    is_legacy_table = False

    if table_exists:
        cursor.execute("""
            SELECT 1 FROM pragma_table_info("favorite_manga")
            WHERE name='manga_id'
        """)
        is_legacy_table = cursor.fetchone() is not None

    if is_legacy_table:
        # Legacy user: table exists but no version record = needs migration
        # We need to insert a version record for migration detection
        cursor.execute(
            "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
            (LEGACY_VERSION, "database"),
        )
    else:
        cursor.execute(
            "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
            (DEFAULT_DATABASE_VERSION, "database"),
        )

    conn.commit()


def init_db(conn: Connection) -> None:
    """Initialize database using provided connection."""
    init_schema_version_table(conn)

    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS favorite_manga (
            id TEXT PRIMARY KEY,
            title TEXT NOT NULL,
            source TEXT NOT NULL
        )
    """)

    conn.commit()


def _get_db_path() -> Path:
    """Get the path to the SQLite database file."""
    config_dir = Path(os.path.expanduser("~/.manga-archiver"))
    config_dir.mkdir(parents=True, exist_ok=True)

    return config_dir / "manga-archiver.db"


def get_connection() -> Connection:
    """Get a connection to the SQLite database."""
    return connect(_get_db_path())
