import asyncio
import json
from pathlib import Path
from typing import TypedDict, cast

from ..constants.defaults import (
    DEFAULT_DATA_SAVER,
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from ..models.app_config import AppConfig
from ..models.output_format import OutputFormat
from .utils import get_root_path

SETTINGS_FILENAME = "settings.json"


class SerializedSettings(TypedDict):
    """Serialized AppConfig fields persisted in the settings store."""

    output_path: str
    output_format: str
    quality: int
    optimize: bool
    data_saver: bool


class SettingsStore:
    """Persists application settings between sessions."""

    def __init__(self, settings_path: Path | None = None) -> None:
        self._settings_path = settings_path or get_root_path() / SETTINGS_FILENAME

    async def load(self) -> AppConfig:
        """Load settings from the settings store."""
        if not await asyncio.to_thread(self._settings_path.exists):
            await asyncio.to_thread(self._settings_path.parent.mkdir, parents=True, exist_ok=True)
            await asyncio.to_thread(
                self._settings_path.write_text,
                json.dumps(_get_default_settings(), indent=2),
            )

        settings_data = await _parse_settings_file(self._settings_path)
        if settings_data is None:
            settings_data = _get_default_settings()

        return _create_app_config(settings_data)

    async def save(self, app_config: AppConfig) -> None:
        """Save settings to the settings store."""
        try:
            AppConfig(
                optimize=app_config.optimize,
                data_saver=app_config.data_saver,
                _output_path=Path(app_config.output_path),
                _output_format=app_config.output_format,
                _quality=app_config.quality,
            )
        except ValueError as e:
            raise ValueError(f"Invalid settings: {e}") from e

        settings_data = SerializedSettings(
            output_path=str(app_config.output_path),
            output_format=str(app_config.output_format),
            quality=app_config.quality,
            optimize=app_config.optimize,
            data_saver=app_config.data_saver,
        )

        try:
            await asyncio.to_thread(
                self._settings_path.write_text,
                json.dumps(settings_data, indent=2),
            )
        except OSError as e:
            raise ValueError(f"Failed to save {SETTINGS_FILENAME}: {e}") from e


def _get_default_settings() -> SerializedSettings:
    return SerializedSettings(
        output_path=str(DEFAULT_OUTPUT_PATH),
        output_format=str(DEFAULT_OUTPUT_FORMAT),
        quality=DEFAULT_QUALITY,
        optimize=DEFAULT_OPTIMIZE,
        data_saver=DEFAULT_DATA_SAVER,
    )


async def _parse_settings_file(settings_path: Path) -> SerializedSettings | None:
    try:
        parsed_settings = json.loads(await asyncio.to_thread(settings_path.read_text))
    except (json.JSONDecodeError, OSError):
        return None

    if not isinstance(parsed_settings, dict):
        return None

    return cast(SerializedSettings, parsed_settings)


def _create_app_config(settings_data: SerializedSettings) -> AppConfig:
    try:
        return AppConfig(
            _output_path=Path(settings_data.get("output_path", str(DEFAULT_OUTPUT_PATH))),
            _output_format=OutputFormat(
                settings_data.get("output_format", str(DEFAULT_OUTPUT_FORMAT))
            ),
            _quality=settings_data.get("quality", DEFAULT_QUALITY),
            optimize=settings_data.get("optimize", DEFAULT_OPTIMIZE),
            data_saver=settings_data.get("data_saver", DEFAULT_DATA_SAVER),
        )
    except (TypeError, ValueError):
        return AppConfig()
