from dataclasses import dataclass
from pathlib import Path

import pytest
from textual.app import App, ComposeResult
from textual.validation import ValidationResult
from textual.widgets import Input, Select, Switch

from src.mangadex_downloader.enums import OutputFormat
from src.mangadex_downloader.widgets.settings_panel import SettingsPanel


@dataclass
class MockValidationResult:
    is_valid: bool = True


def valid_result() -> ValidationResult:
    return MockValidationResult(True)  # type: ignore[return-value]


def invalid_result() -> ValidationResult:
    return MockValidationResult(False)  # type: ignore[return-value]


DEFAULT_OUTPUT_PATH = Path.home() / "Downloads"
DEFAULT_OUTPUT_FORMAT = OutputFormat.PDF
DEFAULT_QUALITY = 75
DEFAULT_OPTIMIZE = False


class SettingsPanelTestApp(App):
    def compose(self) -> ComposeResult:
        yield SettingsPanel(
            output_directory=str(DEFAULT_OUTPUT_PATH),
            output_format=str(DEFAULT_OUTPUT_FORMAT),
            quality=DEFAULT_QUALITY,
            optimize=DEFAULT_OPTIMIZE,
        )


class TestSettingsPanel:
    async def test_settings_panel_get_settings(self):
        app = SettingsPanelTestApp()

        async with app.run_test():
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            settings: dict = settings_panel.get_settings()

            assert settings["output_directory"] == str(DEFAULT_OUTPUT_PATH)
            assert settings["output_format"] == str(DEFAULT_OUTPUT_FORMAT)
            assert settings["quality"] == DEFAULT_QUALITY
            assert settings["optimize"] == DEFAULT_OPTIMIZE

    async def test_toggle_optimize_switch(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            switch: Switch = settings_panel.query_one("#optimize-switch", Switch)

            initial_value: bool = settings_panel._optimize

            await pilot.click(switch)

            assert settings_panel._optimize != initial_value

    async def test_select_output_format(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            select: Select = settings_panel.query_one(Select)

            assert settings_panel._output_format != "cbz"

            select.value = "cbz"

            select.post_message(Select.Changed(select, select.value))  # type: ignore[arg-type]
            await pilot.pause()
            assert settings_panel._output_format == "cbz"

    @pytest.mark.parametrize(
        ("input_value", "validation_result", "expected_quality"),
        [
            ("50", valid_result(), 50),
            ("", valid_result(), DEFAULT_QUALITY),
            ("-1", invalid_result(), DEFAULT_QUALITY),
            ("101", invalid_result(), DEFAULT_QUALITY),
        ],
        ids=["valid", "empty", "below_min", "above_max"],
    )
    async def test_input_quality_various_inputs(
        self, input_value, validation_result, expected_quality
    ):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            input_field: Input = settings_panel.query_one(Input)

            input_field.value = input_value
            input_field.post_message(Input.Changed(input_field, input_value, validation_result))  # type: ignore[arg-type]
            await pilot.pause()

            assert settings_panel._quality == expected_quality
