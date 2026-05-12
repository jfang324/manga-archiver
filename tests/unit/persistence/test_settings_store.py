import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from src.manga_archiver.constants.defaults import (
    DEFAULT_DATA_SAVER,
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.persistence.settings_store import SettingsStore


class TestSettingsStoreLoad:
    def test_load_creates_file_with_defaults_when_missing(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        store = SettingsStore(settings_file)

        config = store.load()

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
        assert config.output_path in (DEFAULT_OUTPUT_PATH, Path.cwd())

    @pytest.mark.parametrize(
        "raw_settings",
        [
            "{ invalid json",
            json.dumps(
                {
                    "output_path": str(Path.cwd()),
                    "output_format": "pdf",
                    "quality": 101,
                    "optimize": False,
                    "data_saver": False,
                }
            ),
            json.dumps(
                {
                    "output_path": "/nonexistent/path/that/doesnt/exist",
                    "output_format": "pdf",
                    "quality": 75,
                    "optimize": False,
                    "data_saver": False,
                }
            ),
        ],
        ids=["malformed_json", "invalid_quality", "invalid_path"],
    )
    def test_load_returns_defaults_when_settings_cannot_build_config(
        self, raw_settings: str, tmp_path: Path
    ) -> None:
        settings_file = tmp_path / "settings.json"
        settings_file.write_text(raw_settings)
        store = SettingsStore(settings_file)

        config = store.load()

        assert config.quality == DEFAULT_QUALITY
        assert config.output_format == DEFAULT_OUTPUT_FORMAT
        assert config.optimize == DEFAULT_OPTIMIZE
        assert config.data_saver == DEFAULT_DATA_SAVER
        assert config.output_path in (DEFAULT_OUTPUT_PATH, Path.cwd())

    def test_load_returns_valid_config(self, tmp_path: Path) -> None:
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
        store = SettingsStore(settings_file)

        config = store.load()

        assert config.quality == 80
        assert config.output_path == tmp_path
        assert config.output_format == OutputFormat.PDF
        assert config.optimize is True
        assert config.data_saver is True


class TestSettingsStoreSave:
    def test_save_writes_valid_config(self, tmp_path: Path) -> None:
        settings_file = tmp_path / "settings.json"
        store = SettingsStore(settings_file)
        config = AppConfig(
            optimize=True,
            data_saver=False,
            _output_path=tmp_path,
            _output_format=OutputFormat.PDF,
            _quality=85,
        )

        store.save(config)

        data = json.loads(settings_file.read_text())
        assert data["quality"] == 85
        assert data["optimize"] is True
        assert data["output_format"] == "pdf"
        assert data["output_path"] == str(tmp_path)
        assert data["data_saver"] is False

    def test_save_raises_on_write_failure(self, tmp_path: Path) -> None:
        mock_path = MagicMock()
        mock_path.write_text.side_effect = OSError("Permission denied")
        store = SettingsStore(mock_path)
        config = AppConfig(
            optimize=False,
            data_saver=False,
            _output_path=tmp_path,
            _output_format=OutputFormat.CBZ,
            _quality=75,
        )

        with pytest.raises(ValueError, match="Failed to save settings"):
            store.save(config)

    @patch("src.manga_archiver.persistence.settings_store.AppConfig")
    def test_save_raises_on_invalid_config(self, mock_config: MagicMock) -> None:
        mock_config.side_effect = ValueError("quality must be between 1 and 100")
        store = SettingsStore(MagicMock())

        with pytest.raises(ValueError, match="Invalid settings"):
            store.save(MagicMock())
