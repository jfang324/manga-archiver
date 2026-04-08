from textual import on
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import SelectionList
from textual.widgets.selection_list import Selection

from src.mangadex_downloader.widgets.selection_panel import SelectionPanel


class SelectionPanelApp(App):
    """Minimal App for testing SelectionPanel."""

    mock_options: reactive[list[tuple[str | None, str, str]]] = reactive(
        [
            ("Title 1", "Value 1", "1"),
            ("Title 2", "Value 2", "2"),
        ]
    )

    def __init__(self) -> None:
        super().__init__()
        self.selection_records: list[SelectionPanel.Selected] = []

    def compose(self) -> ComposeResult:
        yield SelectionPanel(title="Test").data_bind(options=SelectionPanelApp.mock_options)

    @on(SelectionPanel.Selected)
    def _record_selection_message(self, message: SelectionPanel.Selected) -> None:
        self.selection_records.append(message)


class TestSelectionPanel:
    def _format_values(self, values: tuple[str | None, str, str]) -> str:
        """Format a tuple of values for comparison (with prefix for display)."""
        return f"{values[2]}. {values[0]}" if values[0] else values[2]

    def _get_clean_title(self, values: tuple[str | None, str, str]) -> str:
        """Get clean title without chapter prefix."""
        return values[0] if values[0] else "untitled"

    async def test_selecting_option_sends_message(self) -> None:
        app = SelectionPanelApp()

        async with app.run_test() as pilot:
            selection_list: SelectionList = app.query_one("#selection-list", SelectionList)

            selection_list.focus()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.press("ctrl+s")

            selection_records = app.selection_records
            assert len(selection_records) == 1

            message = selection_records.pop()
            assert message.selected_pairs == [
                (
                    self._get_clean_title(app.mock_options[0]),
                    app.mock_options[0][1],
                    app.mock_options[0][2],
                )
            ]

    async def test_selecting_multiple_options_sends_message(self) -> None:
        app = SelectionPanelApp()

        async with app.run_test() as pilot:
            selection_list: SelectionList = app.query_one("#selection-list", SelectionList)

            selection_list.focus()
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.press("down")
            await pilot.press("enter")
            await pilot.press("ctrl+s")

            selection_records = app.selection_records
            assert len(selection_records) == 1

            message = selection_records.pop()
            assert message.selected_pairs == [
                (
                    self._get_clean_title(app.mock_options[0]),
                    app.mock_options[0][1],
                    app.mock_options[0][2],
                ),
                (
                    self._get_clean_title(app.mock_options[1]),
                    app.mock_options[1][1],
                    app.mock_options[1][2],
                ),
            ]

    async def test_selection_options_displays_options(self) -> None:
        app = SelectionPanelApp()

        async with app.run_test():
            selection_list: SelectionList = app.query_one("#selection-list", SelectionList)
            mock_options = app.mock_options

            assert len(selection_list.options) == len(mock_options)

            for index, option in enumerate(mock_options):
                selection_item = selection_list.get_option_at_index(index)

                assert isinstance(selection_item, Selection)
                assert selection_item.prompt == self._format_values(option)
                assert selection_item.value == option[1]
