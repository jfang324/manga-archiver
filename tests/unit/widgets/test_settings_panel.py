from dataclasses import dataclass

from textual.app import App, ComposeResult
from textual.validation import ValidationResult
from textual.widgets import Input, Select, Switch

from src.mangadex_downloader.widgets.settings_panel import SettingsPanel


@dataclass
class MockValidationResult:
    is_valid: bool = True


def valid_result() -> ValidationResult:
    return MockValidationResult(True)  # type: ignore[return-value]


def invalid_result() -> ValidationResult:
    return MockValidationResult(False)  # type: ignore[return-value]


class SettingsPanelTestApp(App):
    def compose(self) -> ComposeResult:
        yield SettingsPanel()


class TestSettingsPanel:
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

    async def test_input_quality_valid(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            input_field: Input = settings_panel.query_one(Input)

            input_field.value = "50"
            input_field.post_message(Input.Changed(input_field, "50", valid_result()))  # type: ignore[arg-type]
            await pilot.pause()

            assert settings_panel._quality == 50

    async def test_input_quality_empty(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            input_field: Input = settings_panel.query_one(Input)

            initial_value: int = settings_panel._quality

            input_field.value = ""
            input_field.post_message(Input.Changed(input_field, "", valid_result()))  # type: ignore[arg-type]
            await pilot.pause()

            assert settings_panel._quality == initial_value

    async def test_input_quality_below_min(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            input_field: Input = settings_panel.query_one(Input)

            initial_value: int = settings_panel._quality

            input_field.value = "-1"
            input_field.post_message(Input.Changed(input_field, "-1", invalid_result()))  # type: ignore[arg-type]
            await pilot.pause()

            assert settings_panel._quality == initial_value

    async def test_input_quality_above_max(self):
        app = SettingsPanelTestApp()

        async with app.run_test() as pilot:
            settings_panel: SettingsPanel = app.query_one(SettingsPanel)
            input_field: Input = settings_panel.query_one(Input)

            initial_value: int = settings_panel._quality

            input_field.value = "101"
            input_field.post_message(
                Input.Changed(input_field, "101", invalid_result())
            )  # type: ignore[arg-type]
            await pilot.pause()

            assert settings_panel._quality == initial_value
