import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mangadex_downloader.constants.defaults import (
    DEFAULT_DATA_SAVER,
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from src.mangadex_downloader.enums import OutputFormat
from src.mangadex_downloader.models.app_config import AppConfig
from src.mangadex_downloader.utils import settings_manager
from src.mangadex_downloader.utils.settings_manager import SettingsData


class TestCreateAppConfig:
    @pytest.mark.parametrize(
        ("settings_data", "expected"),
        [
            (
                SettingsData(
                    quality=80,
                    output_path=str(Path.cwd()),
                    output_format="pdf",
                    optimize=True,
                    data_saver=True,
                ),
                {
                    "quality": 80,
                    "output_path": Path.cwd(),
                    "output_format": OutputFormat.PDF,
                    "optimize": True,
                    "data_saver": True,
                },
            ),
            (
                SettingsData(
                    quality=50,
                    output_path=str(Path.cwd()),
                    output_format="cbz",
                    optimize=False,
                    data_saver=False,
                ),
                {
                    "quality": 50,
                    "output_path": Path.cwd(),
                    "output_format": OutputFormat.CBZ,
                    "optimize": False,
                    "data_saver": False,
                },
            ),
            (
                {
                    "output_path": str(Path.cwd()),
                    "output_format": "pdf",
                },  # missing quality, optimize, data_saver
                {
                    "quality": DEFAULT_QUALITY,
                    "output_path": Path.cwd(),
                    "output_format": DEFAULT_OUTPUT_FORMAT,
                    "optimize": DEFAULT_OPTIMIZE,
                    "data_saver": DEFAULT_DATA_SAVER,
                },
            ),
        ],
        ids=["custom_values", "cbz_format", "missing_fields_uses_defaults"],
    )
    def test_create_app_config_returns_config(self, settings_data, expected):
        config = settings_manager._create_app_config(settings_data)

        assert config.quality == expected["quality"]
        assert config.output_path == expected["output_path"]
        assert config.output_format == expected["output_format"]
        assert config.optimize == expected["optimize"]
        assert config.data_saver == expected["data_saver"]

    def test_create_app_config_invalid_quality_triggers_fallback(self):
        settings_data = SettingsData(
            quality=101,  # invalid - must be 1-100
            output_path=str(Path.cwd()),
            output_format="pdf",
            optimize=False,
            data_saver=False,
        )

        config = settings_manager._create_app_config(settings_data)

        assert config.output_path == Path.cwd()

    def test_create_app_config_fallback_on_invalid_path(self):
        settings_data = SettingsData(
            output_path="/nonexistent/path/that/doesnt/exist",
            output_format="pdf",
            quality=75,
            optimize=False,
            data_saver=False,
        )

        config = settings_manager._create_app_config(settings_data)

        assert config.output_path == Path.cwd()


class TestLoadSettings:
    def test_load_settings_creates_file_with_defaults_when_not_exists(self, tmp_path):
        settings_file = tmp_path / "settings.json"

        with patch.object(
            settings_manager, "_get_settings_path", return_value=settings_file
        ):
            config = settings_manager.load_settings()

        assert settings_file.exists()
        data = json.loads(settings_file.read_text())
        assert data["quality"] == DEFAULT_QUALITY
        assert data["output_format"] == str(DEFAULT_OUTPUT_FORMAT)
        assert data["optimize"] == DEFAULT_OPTIMIZE
        assert data["data_saver"] == DEFAULT_DATA_SAVER

        assert config.quality == DEFAULT_QUALITY
        assert config.output_format == DEFAULT_OUTPUT_FORMAT
        assert config.optimize == DEFAULT_OPTIMIZE
        assert config.data_saver == DEFAULT_DATA_SAVER
        # Note: output_path depends on whether DEFAULT_OUTPUT_PATH exists on the system
        # If it doesn't exist, falls back to Path.cwd()
        assert config.output_path in (DEFAULT_OUTPUT_PATH, Path.cwd())

    def test_load_settings_returns_defaults_on_parse_error(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("{ invalid json")

        with patch.object(
            settings_manager, "_get_settings_path", return_value=settings_file
        ):
            config = settings_manager.load_settings()

        assert config.quality == DEFAULT_QUALITY
        assert config.output_format == DEFAULT_OUTPUT_FORMAT
        assert config.optimize == DEFAULT_OPTIMIZE
        assert config.data_saver == DEFAULT_DATA_SAVER

    def test_load_settings_returns_valid_config(self, tmp_path):
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(
            json.dumps(
                {
                    "output_path": str(tmp_path),
                    "output_format": "pdf",
                    "quality": 80,
                    "optimize": True,
                    "data_saver": True,
                }
            )
        )

        with patch.object(
            settings_manager, "_get_settings_path", return_value=settings_file
        ):
            config = settings_manager.load_settings()

        assert config.quality == 80
        assert config.output_path == tmp_path
        assert config.output_format == OutputFormat.PDF
        assert config.optimize is True
        assert config.data_saver is True


class TestSaveSettings:
    def test_save_settings_writes_valid_config(self, tmp_path):
        settings_file = tmp_path / "settings.json"

        with patch.object(
            settings_manager, "_get_settings_path", return_value=settings_file
        ):
            config = AppConfig(
                optimize=True,
                data_saver=False,
                _output_path=tmp_path,
                _output_format=OutputFormat.PDF,
                _quality=85,
            )

            settings_manager.save_settings(config)

        data = json.loads(settings_file.read_text())
        assert data["quality"] == 85
        assert data["optimize"] is True
        assert data["output_format"] == "pdf"
        assert data["output_path"] == str(tmp_path)
        assert data["data_saver"] is False

    def test_save_settings_raises_on_write_failure(self, tmp_path):
        mock_path = MagicMock()
        mock_path.write_text.side_effect = OSError("Permission denied")

        with patch.object(
            settings_manager, "_get_settings_path", return_value=mock_path
        ):
            config = AppConfig(
                optimize=False,
                data_saver=False,
                _output_path=tmp_path,
                _output_format=OutputFormat.CBZ,
                _quality=75,
            )

            with pytest.raises(ValueError, match="Failed to save settings"):
                settings_manager.save_settings(config)

    def test_save_settings_raises_on_invalid_config(self):
        with patch(
            "src.mangadex_downloader.utils.settings_manager.AppConfig"
        ) as mock_config:
            mock_config.side_effect = ValueError("quality must be between 1 and 100")

            with pytest.raises(ValueError, match="Invalid settings"):
                settings_manager.save_settings(MagicMock())
