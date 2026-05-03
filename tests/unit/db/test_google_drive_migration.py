import importlib
import sys
from sqlite3 import connect
from unittest.mock import AsyncMock, MagicMock, patch

import src.manga_archiver as manga_archiver_package
from src.manga_archiver.db import schema_manager as schema_manager_module
from src.manga_archiver.db.schema_manager import PreparedMigration
from src.manga_archiver.integrations.storage_providers.google_drive.types import (
    GoogleApiStoredToken,
)

sys.modules.setdefault("manga_archiver", manga_archiver_package)
sys.modules.setdefault("manga_archiver.db.schema_manager", schema_manager_module)
v1_1_0 = importlib.import_module("src.manga_archiver.db.migrations.google_drive.v1_1_0")


def _token() -> GoogleApiStoredToken:
    return {
        "token_uri": "https://oauth2.googleapis.com/token",
        "client_id": "client-id",
        "client_secret": "client-secret",
        "refresh_token": "refresh-token",
    }


async def test_migrate_records_version_when_drive_client_initialization_fails() -> None:
    conn = connect(":memory:")
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE schema_version (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            version TEXT NOT NULL,
            system TEXT NOT NULL
        )
    """)

    with (
        patch.object(v1_1_0, "load_token", return_value=_token()),
        patch.object(v1_1_0, "GoogleDriveMigrationClient") as mock_client_class,
    ):
        mock_client = MagicMock()
        mock_client.initialize = AsyncMock(side_effect=RuntimeError("auth failed"))
        mock_client_class.return_value = mock_client

        result = await v1_1_0.migrate("v1.0.0", cursor)

    assert isinstance(result, PreparedMigration)
    message = result.apply(cursor)

    cursor.execute("SELECT version, system FROM schema_version")
    assert message == "Migrated to v1.1.0: Failed to initialize Drive client"
    assert cursor.fetchall() == [("v1.1.0", "google_drive")]
