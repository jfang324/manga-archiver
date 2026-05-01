from argparse import Namespace
from unittest.mock import MagicMock, patch

from src.manga_archiver.cli.presets import get_preset
from src.manga_archiver.constants.exit_codes import EXIT_SUCCESS
from src.manga_archiver.main import (
    _build_async_dependencies,
    _build_configurations,
    _handle_subcommands,
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
    @patch("src.manga_archiver.main.load_settings", return_value=AppConfig())
    def test_build_configurations_uses_selected_preset(self, mock_load_settings) -> None:
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

        pipeline_config, _ = _build_configurations(args)

        mock_load_settings.assert_called_once_with()
        assert pipeline_config.num_resolve_workers == preset.resolve_workers
        assert pipeline_config.num_download_workers == preset.download_workers
        assert pipeline_config.num_merge_workers == preset.merge_workers
        assert pipeline_config.resolve_rate_limit == preset.resolve_rate_limit
        assert pipeline_config.download_rate_limit == preset.download_rate_limit
        assert pipeline_config.resolve_queue_size == preset.queue_size
        assert pipeline_config.download_queue_size == preset.queue_size * 2
        assert pipeline_config.merge_queue_size == preset.queue_size
        assert pipeline_config.upload_queue_size == preset.queue_size

    @patch("src.manga_archiver.main.load_settings", return_value=AppConfig())
    def test_build_configurations_keeps_manual_values_without_preset(
        self, mock_load_settings
    ) -> None:
        args = _make_args(
            resolve_workers=3,
            download_workers=4,
            merge_workers=5,
            resolve_rate_limit=6,
            download_rate_limit=7,
            queue_size=8,
            benchmark=True,
        )

        pipeline_config, _ = _build_configurations(args)

        mock_load_settings.assert_called_once_with()
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
    @patch("src.manga_archiver.main.ContentProviderManager")
    def test_build_async_dependencies_uses_selected_preset_rate_limits(
        self, mock_provider_manager, mock_download_client
    ) -> None:
        args = _make_args(preset="slow")
        preset = get_preset("slow")
        session = MagicMock()

        provider_manager, download_client = _build_async_dependencies(session, args)

        mock_provider_manager.assert_called_once_with(
            session,
            resolve_rate_limit=preset.resolve_rate_limit,
            download_rate_limit=preset.download_rate_limit,
        )
        mock_download_client.assert_called_once_with(session)
        assert provider_manager == mock_provider_manager.return_value
        assert download_client == mock_download_client.return_value

    def test_handle_list_presets_prints_presets_and_exits_successfully(self, capsys) -> None:
        args = _make_args(command="list", list_target="presets")

        exit_code = _handle_subcommands(args)

        captured = capsys.readouterr()
        assert exit_code == EXIT_SUCCESS
        assert "Available presets:" in captured.out
        assert "safe" in captured.out
        assert "slow" in captured.out
        assert "fast" in captured.out
