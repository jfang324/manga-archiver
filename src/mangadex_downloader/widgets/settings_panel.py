from os import getcwd

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.reactive import reactive
from textual.validation import Number
from textual.widget import Widget
from textual.widgets import Input, Label, Select, Switch

from ..models.app_config import OutputFormat
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

    _output_directory: reactive[str] = reactive(".")
    _output_format: reactive[str] = reactive(str(OutputFormat.PDF))
    _quality: reactive[int] = reactive(75)
    _optimize: reactive[bool] = reactive(False)

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._output_directory = getcwd()
        self._output_format = str(OutputFormat.PDF)
        self._quality = 75
        self._optimize = False

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
                    yield (
                        Select(options=[], classes="field-select")
                        .from_values(OutputFormat.list_formats())
                        .data_bind(value=SettingsPanel._output_format)
                    )

                with Vertical(classes="field-container"):
                    yield Label(
                        "Quality:",
                        classes="field-label",
                    )
                    yield Input(
                        type="integer",
                        value=str(self._quality),
                        classes="field-select",
                        validators=[Number(minimum=1, maximum=100)],
                    )

                with Horizontal(classes="field-container"):
                    yield Label(
                        "Optimize:",
                        id="optimize-label",
                    )
                    yield Switch(value=self._optimize, id="optimize-switch").data_bind(
                        value=SettingsPanel._optimize
                    )

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
