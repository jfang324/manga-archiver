import os
import sqlite3
from pathlib import Path


def _get_db_path() -> Path:
    config_dir = Path(os.path.expanduser("~/.mangadex-downloader"))
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir / "mangadex.db"


def get_connection() -> sqlite3.Connection:
    """Get a connection to the SQLite database."""
    return sqlite3.connect(_get_db_path())


def init_db() -> None:
    """Initialize the database and create tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS favorite_manga (
                manga_id TEXT PRIMARY KEY,
                manga_title TEXT NOT NULL
            )
        """)

        conn.commit()
