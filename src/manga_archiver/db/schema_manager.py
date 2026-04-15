import importlib.util
import logging
from collections.abc import Callable
from pathlib import Path
from sqlite3 import Connection, Cursor

from .database import get_connection, init_db
from .migrations import MIN_DATABASE_VERSION, MIN_GOOGLE_DRIVE_VERSION

logger = logging.getLogger(__name__)

MigrationFunc = Callable[[str | None, Cursor], str]
MigrationStep = tuple[str, MigrationFunc]


def _version_key(version: str) -> tuple[int, ...]:
    """Convert version string to sortable tuple. 'v1.10.0' -> (1, 10, 0)."""
    clean = version.lstrip("v")
    return tuple(int(x) for x in clean.split("."))


def _version_compare(a: str, b: str | None) -> int:
    """Compare version strings. Returns 1 if a > b, -1 if a < b, 0 if equal."""
    if b is None:
        return 1  # a is greater than None (needs migration)
    key_a = _version_key(a)
    key_b = _version_key(b)

    max_len = max(len(key_a), len(key_b))
    key_a = key_a + (0,) * (max_len - len(key_a))
    key_b = key_b + (0,) * (max_len - len(key_b))

    for a_part, b_part in zip(key_a, key_b, strict=False):
        if a_part > b_part:
            return 1
        if a_part < b_part:
            return -1

    return 0


class MigrationError(Exception):
    """Raised when migration fails."""

    pass


class SchemaManager:
    """Manages database schema versions and migrations."""

    def __init__(self, conn: Connection | None = None) -> None:
        self._conn = conn or get_connection()

        init_db(self._conn)

    @property
    def conn(self) -> Connection:
        return self._conn

    def insert_version_record(self, system: str, version: str) -> None:
        """Insert a version record for a system if one doesn't exist."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO schema_version (system, version) VALUES (?, ?)",
                (system, version),
            )
            self._conn.commit()
        except Exception as e:
            logger.error("Failed to insert version record: %s", e)

    def get_current_version(self, system: str) -> str | None:
        """Get current schema version for a system."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "SELECT version FROM schema_version WHERE system = ? ORDER BY id DESC LIMIT 1",
                (system,),
            )
            row = cursor.fetchone()

            return row[0] if row else None
        except Exception as e:
            logger.error("Failed to get system version: %s", e)
            return None

    def get_pending_migrations(self, system: str) -> list[MigrationStep]:
        """Get all migration functions greater than current version."""
        current = self.get_current_version(system)
        migrations: list[MigrationStep] = []
        migrations_dir = Path(__file__).parent / "migrations" / system

        if not migrations_dir.exists():
            return []

        for migration_file in migrations_dir.glob("v*.py"):
            version = migration_file.stem.replace("_", ".")
            if _version_compare(version, current) <= 0:
                continue

            migrations.append((version, self._load_migration(migration_file)))

        return sorted(migrations, key=lambda x: _version_key(x[0]))

    def _load_migration(self, path: Path) -> MigrationFunc:
        """Load migration function from file."""
        spec = importlib.util.spec_from_file_location("migration", path)
        if spec is None:
            raise MigrationError(f"Could not load migration from {path}")

        module = importlib.util.module_from_spec(spec)
        if spec.loader is None:
            raise MigrationError(f"Could not load migration from {path}")

        spec.loader.exec_module(module)
        return module.migrate  # type: ignore[return-value]

    def run_migrations(self, system: str) -> str:
        """Run all pending migrations for a single system. Returns result message."""
        pending = self.get_pending_migrations(system)

        if not pending:
            current = self.get_current_version(system)
            return f"Already at {current}"

        cursor = self.conn.cursor()
        current_version = self.get_current_version(system)

        try:
            for migrate_version, migrate_func in pending:
                current = self.get_current_version(system)
                cursor.execute("BEGIN IMMEDIATE")

                migration_msg = migrate_func(current, cursor)
                logging.info(migration_msg)
                self.conn.commit()
                current_version = migrate_version
        except Exception as e:
            self.conn.rollback()
            raise MigrationError(f"Migration {current_version} failed: {e}") from e

        return f"Migrated to {current_version}"

    def check_versions(
        self,
        require_google_drive: bool,
    ) -> tuple[bool, str]:
        """Check if required versions are met.

        Args:
            require_google_drive: Whether Google Drive is required

        Returns:
            tuple[bool, str]: (True, "") if requirements satisfied, (False, error_message) if migration needed
        """
        db_current = self.get_current_version("database")

        if _version_compare(MIN_DATABASE_VERSION, db_current) > 0:
            error_msg = (
                f"Database migration required. "
                f"Current: {db_current}, Required: {MIN_DATABASE_VERSION}. "
                f"Run: manga-archiver migrate database"
            )
            logger.error(error_msg)
            return False, error_msg

        if require_google_drive and MIN_GOOGLE_DRIVE_VERSION is not None:
            google_drive_current = self.get_current_version("google_drive")

            if _version_compare(MIN_GOOGLE_DRIVE_VERSION, google_drive_current) > 0:
                error_msg = (
                    f"Google Drive migration required. "
                    f"Current: {google_drive_current}, Required: {MIN_GOOGLE_DRIVE_VERSION}. "
                    f"Run: manga-archiver migrate google-drive"
                )
                logger.error(error_msg)
                return False, error_msg

        return True, ""
