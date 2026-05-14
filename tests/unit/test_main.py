from argparse import Namespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.manga_archiver.cli.handlers import handle_workflow_subcommands
from src.manga_archiver.cli.presets import get_preset
from src.manga_archiver.constants.exit_codes import (
    EXIT_AUTH_ERROR,
    EXIT_AUTH_LOGIN_FAILED,
    EXIT_AUTH_LOGOUT_FAILED,
    EXIT_MIGRATION_ERROR,
    EXIT_SUCCESS,
)
from src.manga_archiver.integrations.webhooks import WebhookProvider
from src.manga_archiver.main import (
    _build_async_dependencies,
    _build_configurations,
    _initialize_google_drive,
)
from src.manga_archiver.models.app_config import AppConfig


def _make_args(**overrides: object) -> Namespace:
    defaults = {
        "preset": None,
        "resolve_workers": 2,
        "download_workers": 2,
        "merge_workers": 2,
        "resolve_rate_limit": 10,
        "download_rate_limit": 20,
        "queue_size": 2,
        "benchmark": False,
        "command": None,
    }
    defaults.update(overrides)
    return Namespace(**defaults)


class TestPresets:
    async def test_build_configurations_uses_selected_preset(self) -> None:
        args = _make_args(
            preset="fast",
            resolve_workers=1,
            download_workers=1,
            merge_workers=1,
            resolve_rate_limit=1,
            download_rate_limit=1,
            queue_size=1,
        )
        preset = get_preset("fast")
        settings_store = MagicMock()
        settings_store.load = AsyncMock(return_value=AppConfig())

        pipeline_config, _ = await _build_configurations(args, settings_store)

        settings_store.load.assert_awaited_once_with()
        assert pipeline_config.num_resolve_workers == preset.resolve_workers
        assert pipeline_config.num_download_workers == preset.download_workers
        assert pipeline_config.num_merge_workers == preset.merge_workers
        assert pipeline_config.resolve_rate_limit == preset.resolve_rate_limit
        assert pipeline_config.download_rate_limit == preset.download_rate_limit
        assert pipeline_config.resolve_queue_size == preset.queue_size
        assert pipeline_config.download_queue_size == preset.queue_size * 2
        assert pipeline_config.merge_queue_size == preset.queue_size
        assert pipeline_config.upload_queue_size == preset.queue_size

    async def test_build_configurations_keeps_manual_values_without_preset(self) -> None:
        args = _make_args(
            resolve_workers=3,
            download_workers=4,
            merge_workers=5,
            resolve_rate_limit=6,
            download_rate_limit=7,
            queue_size=8,
            benchmark=True,
        )
        settings_store = MagicMock()
        settings_store.load = AsyncMock(return_value=AppConfig())

        pipeline_config, _ = await _build_configurations(args, settings_store)

        settings_store.load.assert_awaited_once_with()
        assert pipeline_config.num_resolve_workers == 3
        assert pipeline_config.num_download_workers == 4
        assert pipeline_config.num_merge_workers == 5
        assert pipeline_config.resolve_rate_limit == 6
        assert pipeline_config.download_rate_limit == 7
        assert pipeline_config.resolve_queue_size == 8
        assert pipeline_config.download_queue_size == 16
        assert pipeline_config.merge_queue_size == 8
        assert pipeline_config.upload_queue_size == 8
        assert pipeline_config.benchmark_enabled is True

    @patch("src.manga_archiver.main.DownloadClient")
    @patch("src.manga_archiver.main.WebhookClient")
    @patch("src.manga_archiver.main.ContentProviderManager")
    async def test_build_async_dependencies_uses_selected_preset_rate_limits(
        self, mock_provider_manager, mock_webhook_client, mock_download_client
    ) -> None:
        args = _make_args(preset="slow")
        preset = get_preset("slow")
        session = MagicMock()
        webhook_config_store = MagicMock()
        webhook_config_store.load = AsyncMock(return_value={})
        webhook_config_store.get_enabled_webhooks.return_value = []

        provider_manager, download_client, webhook_client = await _build_async_dependencies(
            session, args, webhook_config_store
        )

        mock_provider_manager.assert_called_once_with(
            session,
            resolve_rate_limit=preset.resolve_rate_limit,
            download_rate_limit=preset.download_rate_limit,
        )
        mock_download_client.assert_called_once_with(session)
        webhook_config_store.load.assert_awaited_once_with()
        webhook_config_store.get_enabled_webhooks.assert_called_once_with({})
        mock_webhook_client.assert_called_once_with(
            session=session,
            providers=[],
            config={},
        )
        assert provider_manager == mock_provider_manager.return_value
        assert download_client == mock_download_client.return_value
        assert webhook_client == mock_webhook_client.return_value

    async def test_initialize_google_drive_returns_auth_error_when_no_token(self) -> None:
        schema_manager = MagicMock()
        token_store = MagicMock()
        token_store.load = AsyncMock(return_value=None)

        result = await _initialize_google_drive(schema_manager, token_store)

        token_store.load.assert_awaited_once_with()
        assert result.exit_code == EXIT_AUTH_ERROR
        assert result.archive_store is None
        assert result.folder_cache is None

    async def test_handle_list_presets_prints_presets_and_exits_successfully(self, capsys) -> None:
        args = _make_args(command="list", list_target="presets")

        exit_code = await handle_workflow_subcommands(args, MagicMock())

        captured = capsys.readouterr()
        assert exit_code == EXIT_SUCCESS
        assert "Available presets:" in captured.out
        assert "safe" in captured.out
        assert "slow" in captured.out
        assert "fast" in captured.out

    @patch("builtins.input", return_value="no")
    async def test_handle_config_disable_preserves_existing_webhook_url(
        self, mock_input: MagicMock, capsys
    ) -> None:
        existing_url = "https://example.com/webhook"
        args = _make_args(
            command="config",
            config_category="webhooks",
            config_target="discord",
        )
        webhook_config_store = MagicMock()
        webhook_config_store.load = AsyncMock(
            return_value={
                WebhookProvider.DISCORD: {
                    "enabled": True,
                    "webhook_url": existing_url,
                }
            }
        )
        webhook_config_store.save_config = AsyncMock()

        exit_code = await handle_workflow_subcommands(args, webhook_config_store)

        captured = capsys.readouterr()
        mock_input.assert_called_once_with("Enable Discord webhook notifications? [y/n]: ")
        webhook_config_store.load.assert_awaited_once_with()
        webhook_config_store.save_config.assert_awaited_once_with(
            WebhookProvider.DISCORD,
            {
                "enabled": False,
                "webhook_url": existing_url,
            },
        )
        assert exit_code == EXIT_SUCCESS
        assert "Discord webhook config saved." in captured.out
        assert captured.err == ""

    @pytest.mark.parametrize(
        ("auth_action", "handler_name", "exit_code", "message"),
        [
            ("login", "handle_auth_login", EXIT_AUTH_LOGIN_FAILED, "login called"),
            ("logout", "handle_auth_logout", EXIT_AUTH_LOGOUT_FAILED, "logout called"),
        ],
        ids=["login", "logout"],
    )
    @patch("src.manga_archiver.cli.handlers.handle_auth_logout")
    @patch("src.manga_archiver.cli.handlers.handle_auth_login")
    async def test_handle_auth_delegates_and_returns_exit_code(
        self,
        mock_handle_auth_login: MagicMock,
        mock_handle_auth_logout: MagicMock,
        auth_action: str,
        handler_name: str,
        exit_code: int,
        message: str,
        capsys,
    ) -> None:
        mock_handler = (
            mock_handle_auth_login
            if handler_name == "handle_auth_login"
            else mock_handle_auth_logout
        )

        async def fake_handler() -> int:
            print(message)
            return exit_code

        mock_handler.side_effect = fake_handler
        args = _make_args(
            command="auth",
            auth_provider="google-drive",
            auth_action=auth_action,
        )

        actual_exit_code = await handle_workflow_subcommands(args, MagicMock())

        captured = capsys.readouterr()
        mock_handler.assert_awaited_once_with()
        assert actual_exit_code == exit_code
        assert message in captured.out
        assert captured.err == ""

    @pytest.mark.parametrize(
        ("migrate_system", "expected_system"),
        [("database", "database"), ("google-drive", "google_drive")],
        ids=["database", "google-drive"],
    )
    @patch("src.manga_archiver.cli.handlers.SchemaManager")
    async def test_handle_migrate_runs_migration_and_exits_successfully(
        self,
        mock_schema_manager: MagicMock,
        migrate_system: str,
        expected_system: str,
        capsys,
    ) -> None:
        schema_manager = MagicMock()
        schema_manager.run_migrations = AsyncMock(
            return_value=f"{expected_system} migration complete"
        )
        mock_schema_manager.return_value = schema_manager
        args = _make_args(command="migrate", migrate_system=migrate_system)

        exit_code = await handle_workflow_subcommands(args, MagicMock())

        captured = capsys.readouterr()
        mock_schema_manager.assert_called_once_with()
        schema_manager.run_migrations.assert_awaited_once_with(expected_system)
        assert exit_code == EXIT_SUCCESS
        assert "Running migrations..." in captured.out
        assert f"{expected_system} migration complete" in captured.out
        assert captured.err == ""

    @pytest.mark.parametrize(
        ("migrate_system", "expected_system"),
        [("database", "database"), ("google-drive", "google_drive")],
        ids=["database", "google-drive"],
    )
    @patch("src.manga_archiver.cli.handlers.SchemaManager")
    async def test_handle_migrate_failure_exits_with_migration_error(
        self,
        mock_schema_manager: MagicMock,
        migrate_system: str,
        expected_system: str,
        capsys,
    ) -> None:
        schema_manager = MagicMock()
        schema_manager.run_migrations = AsyncMock(
            side_effect=RuntimeError(f"{expected_system} failed")
        )
        mock_schema_manager.return_value = schema_manager
        args = _make_args(command="migrate", migrate_system=migrate_system)

        exit_code = await handle_workflow_subcommands(args, MagicMock())

        captured = capsys.readouterr()
        mock_schema_manager.assert_called_once_with()
        schema_manager.run_migrations.assert_awaited_once_with(expected_system)
        assert exit_code == EXIT_MIGRATION_ERROR
        assert "Running migrations..." in captured.out
        assert f"Migration failed: {expected_system} failed" in captured.out
        assert captured.err == ""
