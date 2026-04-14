import os
from pathlib import Path
from sqlite3 import Connection, connect

from .migrations import DEFAULT_DATABASE_VERSION, MIN_DATABASE_VERSION


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

    if table_exists:
        version = DEFAULT_DATABASE_VERSION
    else:
        version = MIN_DATABASE_VERSION

    cursor.execute(
        "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
        (version, "database"),
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
            source TEXT NOT NULL DEFAULT 'mangadex'
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
