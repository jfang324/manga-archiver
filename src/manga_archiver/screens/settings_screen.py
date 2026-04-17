from pathlib import Path

from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..constants.defaults import (
    DEFAULT_DATA_SAVER,
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from ..models import AppConfig
from ..models.output_format import OutputFormat
from ..widgets import SettingsPanel


class SettingsScreen(Screen):
    """Settings screen for the application.

    Reactive Attributes:
        app_config (AppConfig): The application configuration
    """

    class Save(Message):
        """Message to schedule settings saving.

        Attributes:
            app_config (AppConfig): The application configuration
        """

        def __init__(self, app_config: AppConfig, **kwargs) -> None:
            super().__init__(**kwargs)

            self.app_config = app_config

    BINDINGS = [("ctrl+s", "save_settings", "Save")]

    app_config: reactive[AppConfig] = reactive(AppConfig)

    _output_directory: reactive[str] = reactive(str(DEFAULT_OUTPUT_PATH))
    _output_format: reactive[str] = reactive(str(DEFAULT_OUTPUT_FORMAT))
    _quality: reactive[int] = reactive(DEFAULT_QUALITY)
    _optimize: reactive[bool] = reactive(DEFAULT_OPTIMIZE)

    def compose(self) -> ComposeResult:
        yield SettingsPanel(
            output_directory=self._output_directory,
            output_format=self._output_format,
            quality=self._quality,
            optimize=self._optimize,
        )
        yield Footer()

    def _sync_from_config(self) -> None:
        self._output_directory = str(self.app_config.output_path)
        self._output_format = str(self.app_config.output_format)
        self._quality = self.app_config.quality
        self._optimize = self.app_config.optimize

    async def on_screen_resume(self) -> None:
        self._sync_from_config()
        settings_panel: SettingsPanel = self.query_one(SettingsPanel)
        settings_panel.remove()

        await self.mount(
            SettingsPanel(
                output_directory=self._output_directory,
                output_format=self._output_format,
                quality=self._quality,
                optimize=self._optimize,
            ),
            before=settings_panel,
        )

    def watch_app_config(self) -> None:
        self._sync_from_config()

    def action_save_settings(self) -> None:
        settings_panel: SettingsPanel = self.query_one(SettingsPanel)
        new_settings = settings_panel.get_settings()

        try:
            config = AppConfig(
                _output_path=Path(new_settings["output_directory"]),
                _output_format=OutputFormat(new_settings["output_format"]),
                _quality=new_settings["quality"],
                optimize=new_settings["optimize"],
                data_saver=DEFAULT_DATA_SAVER,
            )
        except ValueError:
            self.app.notify("Invalid settings values", severity="error")
            return

        self.post_message(SettingsScreen.Save(config))
