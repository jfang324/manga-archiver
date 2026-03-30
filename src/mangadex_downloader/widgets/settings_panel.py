from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.validation import Number
from textual.widget import Widget
from textual.widgets import Input, Label, Select, Switch

from ..constants.defaults import (
    DEFAULT_OPTIMIZE,
    DEFAULT_OUTPUT_FORMAT,
    DEFAULT_OUTPUT_PATH,
    DEFAULT_QUALITY,
)
from ..enums import OutputFormat
from .directory_explorer import DirectoryExplorer


class SettingsPanel(Widget):
    """Settings panel widget for configuring application settings."""

    DEFAULT_CSS = """
    SettingsPanel {
        border: solid $primary;
        height: 1fr;
        padding: 0 1;
    }

    #directory-explorer {
        width: 1fr;
    }

    #other-settings {
        border: solid $primary;
        width: 3fr;
        padding: 0 1;
    }

    .field-container {
        width: 1fr;
        height: auto;
        margin-top: 1;
    }

    .field-label {
        padding: 0 1;
        content-align: left bottom;
        border-bottom:  $primary 0%;
    }

    .field-select {
        width: 1fr;
    }

    #optimize-label {
        padding: 0 1;
        content-align: left bottom;
        width: 1fr;
        height: auto;
        border: solid $primary 0%;
    }

    #optimize-switch {
        width: auto;
    }
    """

    _output_directory: reactive[str] = reactive(str(DEFAULT_OUTPUT_PATH))
    _output_format: reactive[str] = reactive(str(DEFAULT_OUTPUT_FORMAT))
    _quality: reactive[int] = reactive(DEFAULT_QUALITY)
    _optimize: reactive[bool] = reactive(DEFAULT_OPTIMIZE)

    def __init__(
        self,
        output_directory: str,
        output_format: str,
        quality: int,
        optimize: bool,
        **kwargs,
    ) -> None:
        """
        Initialize the settings panel.

        Args:
            output_directory (str): The directory to save output files
            output_format (str): The output format (PDF, CBZ, etc.)
            quality (int): The quality setting for output
            optimize (bool): Whether to optimize output file size
        """
        super().__init__(**kwargs)

        self._output_directory = output_directory
        self._output_format = output_format
        self._quality = quality
        self._optimize = optimize

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield DirectoryExplorer(
                title="Output Directory", id="directory-explorer"
            ).data_bind(current_directory=SettingsPanel._output_directory)

            with Vertical(id="other-settings"):
                with Vertical(classes="field-container"):
                    yield Label(
                        "Output Format:",
                        classes="field-label",
                    )
                    yield Select.from_values(
                        OutputFormat.list_formats(),
                        value=str(self._output_format),
                        classes="field-select",
                    )

                with Vertical(classes="field-container"):
                    yield Label(
                        "Quality:",
                        classes="field-label",
                    )
                    yield Input(
                        type="integer",
                        classes="field-select",
                        value=str(self._quality),
                        validators=[Number(minimum=1, maximum=100)],
                        id="quality-input",
                    )

                with Horizontal(classes="field-container"):
                    yield Label(
                        "Optimize:",
                        id="optimize-label",
                    )
                    yield Switch(value=self._optimize, id="optimize-switch")

    @on(DirectoryExplorer.DirectoryChanged)
    def _update_output_directory(
        self, event: DirectoryExplorer.DirectoryChanged
    ) -> None:
        self._output_directory = event.new_directory

    @on(Select.Changed)
    def _update_output_format(self, event: Select.Changed) -> None:
        str_format = str(event.value)

        if str_format not in OutputFormat.list_formats():
            self.log.error(f"Invalid output format: {str_format}")
            self.notify("Invalid output format", severity="error")
            return

        self._output_format = str_format

    def watch_quality(self, quality: int) -> None:
        quality_input: Input = self.query_one("#quality-input", Input)
        quality_input.value = str(quality)

    @on(Input.Changed)
    def _update_quality(self, event: Input.Changed) -> None:
        if not event.value:
            self.notify("Quality cannot be empty", severity="error")
            return

        if not event.validation_result:
            self.notify("Cannot use un-validated input", severity="error")
            return

        if not event.validation_result.is_valid:
            self.notify("Invalid quality value", severity="error")
            return

        self._quality = int(event.value)

    @on(Switch.Changed)
    def _update_optimize(self, event: Switch.Changed) -> None:
        self._optimize = event.value

    def get_settings(self) -> dict:
        settings: dict = {
            "output_directory": self._output_directory,
            "output_format": self._output_format,
            "quality": self._quality,
            "optimize": self._optimize,
        }

        return settings
