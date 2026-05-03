import asyncio
from sqlite3 import Cursor, connect

import pytest

from src.manga_archiver.db.database import init_schema_version_table
from src.manga_archiver.db.migrations import DEFAULT_DATABASE_VERSION
from src.manga_archiver.db.schema_manager import (
    MigrationStep,
    PreparedMigration,
    SchemaManager,
    _version_compare,
    _version_key,
)


class TestVersionKey:
    @pytest.mark.parametrize(
        "version, expected",
        [
            ("v1.10.0", (1, 10, 0)),
            ("v1.9.0", (1, 9, 0)),
            ("v1.2.3", (1, 2, 3)),
            ("v2.0.0", (2, 0, 0)),
            ("1.2.3", (1, 2, 3)),
            ("v1.0", (1, 0)),
            ("v1", (1,)),
            ("v1.2.3.4", (1, 2, 3, 4)),
        ],
        ids=[
            "v1_10_0",
            "v1_9_0",
            "v1_2_3",
            "v2_0_0",
            "without_v_prefix",
            "single_minor",
            "single_component",
            "four_components",
        ],
    )
    def test_version_key_parses_correctly(self, version: str, expected: tuple[int, ...]) -> None:
        assert _version_key(version) == expected


class TestVersionCompare:
    @pytest.mark.parametrize(
        "a, b, expected",
        [
            ("v1.10.0", "v1.9.0", 1),
            ("v1.9.0", "v1.10.0", -1),
            ("v1.2.0", "v1.2.0", 0),
            ("v1", "v1.0.0", 0),
            ("v2.0.0", "v1.9.9", 1),
            ("v1.2.3", "v1.2.4", -1),
            ("v1.2.5", "v1.2.4", 1),
            ("v1.2", "v1.2.0", 0),
        ],
        ids=[
            "v1_10_greater_than_v1_9",
            "v1_9_less_than_v1_10",
            "v1_2_0_equal_v1_2_0",
            "single_component_equal_to_three",
            "v2_greater_than_v1",
            "v1_2_3_less_than_v1_2_4",
            "v1_2_5_greater_than_v1_2_4",
            "two_components_equal_three_with_zeros",
        ],
    )
    def test_version_compare_returns_correct_result(self, a: str, b: str, expected: int) -> None:
        assert _version_compare(a, b) == expected

    def test_version_compare_greater_than_none(self) -> None:
        assert _version_compare("v1.0.0", None) == 1


class TestSchemaManager:
    def test_insert_version_record_does_not_consume_id_for_duplicate_record(self) -> None:
        conn = connect(":memory:")
        manager = SchemaManager(conn)

        manager.insert_version_record("google_drive", "v1.0.0")
        manager.insert_version_record("google_drive", "v1.0.0")
        manager.insert_version_record("google_drive", "v1.1.0")

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, system, version FROM schema_version WHERE system = ? ORDER BY id",
            ("google_drive",),
        )

        assert cursor.fetchall() == [
            (2, "google_drive", "v1.0.0"),
            (3, "google_drive", "v1.1.0"),
        ]

    def test_init_schema_version_table_does_not_consume_id_on_repeat_initialization(self) -> None:
        conn = connect(":memory:")

        init_schema_version_table(conn)
        init_schema_version_table(conn)

        cursor = conn.cursor()
        cursor.execute(
            "SELECT id, system, version FROM schema_version WHERE system = ? ORDER BY id",
            ("database",),
        )

        assert cursor.fetchall() == [(1, "database", DEFAULT_DATABASE_VERSION)]

    async def test_run_migrations_awaits_prepare_before_write_transaction(self) -> None:
        events: list[str] = []

        class AsyncPreparedMigrationSchemaManager(SchemaManager):
            def get_current_version(self, system: str) -> str | None:
                assert system == "async_test"
                return None

            def get_pending_migrations(self, system: str) -> list[MigrationStep]:
                assert system == "async_test"
                return [("v9.9.9", async_migrate)]

        async def async_migrate(_current: str | None, _cursor: Cursor) -> PreparedMigration:
            events.append("prepare")
            await asyncio.sleep(0)

            def apply(cursor: Cursor) -> str:
                events.append("apply")
                cursor.execute(
                    "INSERT OR IGNORE INTO schema_version (version, system) VALUES (?, ?)",
                    ("v9.9.9", "async_test"),
                )
                return "prepared migration applied"

            return PreparedMigration(apply=apply)

        conn = connect(":memory:")
        conn.set_trace_callback(
            lambda statement: events.append(statement) if statement == "BEGIN IMMEDIATE" else None
        )
        manager = AsyncPreparedMigrationSchemaManager(conn)

        result = await manager.run_migrations("async_test")

        cursor = conn.cursor()
        cursor.execute(
            "SELECT version, system FROM schema_version WHERE system = ?",
            ("async_test",),
        )
        assert result == "Migrated to v9.9.9"
        assert cursor.fetchone() == ("v9.9.9", "async_test")
        assert events.index("prepare") < events.index("BEGIN IMMEDIATE") < events.index("apply")
