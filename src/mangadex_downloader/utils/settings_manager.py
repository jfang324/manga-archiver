import json
import logging
import os
from pathlib import Path
from typing import TypedDict

from ..constants.defaults import (
    DEFAULT_DATA_SAVER,
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from ..enums import OutputFormat
from ..models import AppConfig

logger = logging.getLogger(__name__)

SETTINGS_FILENAME = "settings.json"


class SettingsData(TypedDict):
    """Dictionary containing settings data."""

    output_path: str
    output_format: str
    quality: int
    optimize: bool
    data_saver: bool


def _get_settings_path() -> Path:
    """Get the absolute path to the settings file."""
    config_dir = Path(os.path.expanduser("~/.mangadex-downloader"))

    return config_dir / SETTINGS_FILENAME


def _get_default_settings() -> SettingsData:
    """Get the default settings as a dictionary."""

    return SettingsData(
        output_path=str(DEFAULT_OUTPUT_PATH),
        output_format=str(DEFAULT_OUTPUT_FORMAT),
        quality=DEFAULT_QUALITY,
        optimize=DEFAULT_OPTIMIZE,
        data_saver=DEFAULT_DATA_SAVER,
    )


def _parse_settings_file(settings_path: Path) -> SettingsData | None:
    """Read and parse settings JSON file.

    Args:
        settings_path: Path to settings.json

    Returns:
        SettingsData if successful, None if file cannot be read or parsed
    """
    try:
        return json.loads(settings_path.read_text())
    except (json.JSONDecodeError, OSError):
        return None


def _create_app_config(settings_data: SettingsData) -> AppConfig:
    """Create an AppConfig object from a dictionary of settings data."""
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
    except ValueError as e:
        logger.error("Configuration validation failed: %s. Using default settings instead.", e)
        # Use current working directory as fallback since DEFAULT_OUTPUT_PATH
        # may not exist (e.g., CI environment or deleted Downloads folder).
        # This is a safe fallback as cwd is guaranteed to exist.
        return AppConfig(_output_path=Path.cwd())


def load_settings() -> AppConfig:
    """Load settings from settings.json.

    If settings.json doesn't exist, creates one with default settings.
    If the file cannot be read or contains invalid values, falls back to
    defaults and continues without raising an error.

    Returns:
        AppConfig: The loaded configuration (may be defaults if loading failed)
    """
    settings_path: Path = _get_settings_path()
    config_dir: Path = settings_path.parent

    if not settings_path.exists():
        config_dir.mkdir(parents=True, exist_ok=True)
        default_settings: SettingsData = _get_default_settings()
        settings_path.write_text(json.dumps(default_settings, indent=2))
        logger.info("Settings file not found at %s, created with defaults", settings_path)

    settings_data: SettingsData | None = _parse_settings_file(settings_path)

    if settings_data is None:
        logger.error("Failed to read settings.json from %s", settings_path)
        settings_data = _get_default_settings()
    else:
        logger.info("Loaded settings from %s: %s", settings_path, settings_data)

    return _create_app_config(settings_data)


def save_settings(app_config: AppConfig) -> None:
    """Save settings to settings.json.

    Args:
        app_config: The configuration to save

    Raises:
        ValueError: If settings cannot be saved
    """
    # Validate the settings before saving
    try:
        AppConfig(
            optimize=app_config.optimize,
            data_saver=app_config.data_saver,
            _output_path=Path(app_config.output_path),
            _output_format=app_config.output_format,
            _quality=app_config.quality,
        )
    except ValueError as e:
        logger.error("Invalid settings: %s", e)
        raise ValueError(f"Invalid settings: {e}") from e

    settings_path: Path = _get_settings_path()
    settings_data: SettingsData = SettingsData(
        output_path=str(app_config.output_path),
        output_format=str(app_config.output_format),
        quality=app_config.quality,
        optimize=app_config.optimize,
        data_saver=app_config.data_saver,
    )

    try:
        settings_path.write_text(json.dumps(settings_data, indent=2))
        logger.info("Saved settings to %s: %s", settings_path, settings_data)
    except OSError as e:
        logger.error("Failed to save settings.json to %s: %s", settings_path, e)
        raise ValueError(f"Failed to save settings.json: {e}") from e
