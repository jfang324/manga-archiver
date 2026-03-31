import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.mangadex_downloader.enums import OutputFormat
from src.mangadex_downloader.models.app_config import AppConfig
from src.mangadex_downloader.utils import settings_manager


class TestLoadSettings:
    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    @patch("src.mangadex_downloader.utils.settings_manager._get_default_settings")
    def test_load_settings_creates_file_with_defaults_when_not_exists(
        self, mock_defaults, mock_get_path
    ):
        temp_dir = tempfile.mkdtemp()
        mock_get_path.return_value = Path(temp_dir) / "settings.json"
        mock_defaults.return_value = {
            "output_path": temp_dir,
            "output_format": "pdf",
            "quality": 75,
            "optimize": False,
            "data_saver": False,
        }

        config = settings_manager.load_settings()
        default_config = AppConfig(_output_path=Path(temp_dir))

        assert config.quality == default_config.quality
        assert config.optimize == default_config.optimize
        assert config.data_saver == default_config.data_saver
        assert config.output_format == default_config.output_format

    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    @patch("src.mangadex_downloader.utils.settings_manager._get_default_settings")
    def test_load_settings_returns_defaults_on_corrupted_json(
        self, mock_defaults, mock_get_path
    ):
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "settings.json"
        temp_path.write_text("{ invalid json")
        mock_get_path.return_value = temp_path
        mock_defaults.return_value = {
            "output_path": temp_dir,
            "output_format": "pdf",
            "quality": 75,
            "optimize": False,
            "data_saver": False,
        }

        config = settings_manager.load_settings()
        default_config = AppConfig(_output_path=Path(temp_dir))

        assert config.quality == default_config.quality
        assert config.optimize == default_config.optimize
        assert config.data_saver == default_config.data_saver
        assert config.output_format == default_config.output_format

    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    @patch("src.mangadex_downloader.utils.settings_manager._get_default_settings")
    def test_load_settings_returns_defaults_on_invalid_values(
        self, mock_defaults, mock_get_path
    ):
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "settings.json"
        temp_path.write_text(json.dumps({"quality": 999}))
        mock_get_path.return_value = temp_path
        mock_defaults.return_value = {
            "output_path": temp_dir,
            "output_format": "pdf",
            "quality": 75,
            "optimize": False,
            "data_saver": False,
        }

        config = settings_manager.load_settings()
        default_config = AppConfig(_output_path=Path(temp_dir))

        assert config.quality == default_config.quality

    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    def test_load_settings_returns_valid_config(self, mock_get_path):
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "settings.json"
        temp_path.write_text(
            json.dumps(
                {
                    "output_path": str(temp_dir),
                    "output_format": "pdf",
                    "quality": 80,
                    "optimize": True,
                    "data_saver": True,
                }
            )
        )
        mock_get_path.return_value = temp_path

        config = settings_manager.load_settings()

        assert config.quality == 80
        assert config.optimize is True
        assert config.data_saver is True
        assert config.output_format == OutputFormat.PDF
        assert config.output_path == Path(temp_dir)


class TestSaveSettings:
    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    def test_save_settings_writes_valid_config(self, mock_get_path):
        temp_dir = tempfile.mkdtemp()
        temp_path = Path(temp_dir) / "settings.json"
        mock_get_path.return_value = temp_path

        config = AppConfig(
            optimize=True,
            data_saver=False,
            _output_path=Path(temp_dir),
            _output_format=OutputFormat.PDF,
            _quality=85,
        )

        settings_manager.save_settings(config)

        assert temp_path.exists()
        data = json.loads(temp_path.read_text())
        assert data["quality"] == 85
        assert data["optimize"] is True
        assert data["output_format"] == "pdf"
        assert data["output_path"] == str(temp_dir)
        assert data["data_saver"] is False

    @patch("src.mangadex_downloader.utils.settings_manager._get_settings_path")
    def test_save_settings_raises_on_write_failure(self, mock_get_path):
        mock_path = MagicMock()
        mock_path.write_text.side_effect = OSError("Permission denied")
        mock_get_path.return_value = mock_path

        config = AppConfig(
            optimize=False,
            data_saver=False,
            _output_path=Path(tempfile.mkdtemp()),
            _output_format=OutputFormat.CBZ,
            _quality=75,
        )

        with pytest.raises(ValueError, match="Failed to save settings"):
            settings_manager.save_settings(config)
