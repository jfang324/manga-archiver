import asyncio

from textual import on
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Input, ListView

from src.mangadex_downloader.widgets.search_panel import SearchItem, SearchPanel

DEBOUNCE_DURATION = 50


class SearchPanelApp(App):
    """Minimal App for testing SearchPanel."""

    mock_results: reactive[list[tuple[str, str]]] = reactive(
        [
            ("Title 1", "Value 1"),
            ("Title 2", "Value 2"),
        ]
    )

    def __init__(self) -> None:
        super().__init__()
        self.search_records: list[SearchPanel.Search] = []
        self.selected_records: list[SearchPanel.Selected] = []
        self.favorite_records: list[SearchPanel.Favorite] = []

    def compose(self) -> ComposeResult:
        # smaller debounce duration to avoid sync issues
        yield SearchPanel(debounce_duration=(DEBOUNCE_DURATION // 2)).data_bind(
            results=SearchPanelApp.mock_results
        )

    @on(SearchPanel.Search)
    def _record_search_message(self, message: SearchPanel.Search) -> None:
        self.search_records.append(message)

    @on(SearchPanel.Selected)
    def _record_selected_message(self, message: SearchPanel.Selected) -> None:
        self.selected_records.append(message)

    @on(SearchPanel.Favorite)
    def _record_favorite_message(self, message: SearchPanel.Favorite) -> None:
        self.favorite_records.append(message)


class TestSearchPanel:
    async def test_searching_for_query_sends_message(self) -> None:
        app = SearchPanelApp()

        async with app.run_test():
            search_input: Input = app.query_one("#search-input", Input)

            search_input.value = "test"
            await asyncio.sleep(0.1)

            search_records = app.search_records
            assert len(search_records) == 1

            message = search_records.pop()
            assert message.query == "test"

    async def test_selecting_result_sends_message(self) -> None:
        app = SearchPanelApp()

        async with app.run_test() as pilot:
            search_input: Input = app.query_one("#search-input", Input)

            search_input.value = "test"
            await asyncio.sleep(0.1)

            search_results: ListView = app.query_one("#search-results", ListView)

            search_results.focus()
            await pilot.press("down")
            await pilot.press("enter")

            selected_records = app.selected_records
            assert len(selected_records) == 1

            message = selected_records.pop()
            assert message.value == "Value 1"

    async def test_search_results_displays_results(self) -> None:
        app = SearchPanelApp()

        async with app.run_test():
            search_results: ListView = app.query_one("#search-results", ListView)
            mock_results = app.mock_results

            assert len(search_results.children) == len(mock_results)

            for index, result in enumerate(mock_results):
                search_item = search_results.children[index]

                assert isinstance(search_item, SearchItem)
                assert search_item.title == result[0]

    async def test_search_debounces_properly(self) -> None:
        app = SearchPanelApp()

        async with app.run_test():
            search_input: Input = app.query_one("#search-input", Input)

            search_input.value = "first"
            search_input.value = "second"

            await asyncio.sleep(0.1)

            search_records = app.search_records
            assert len(search_records) == 1

            message = search_records.pop()
            assert message.query == "second"

    async def test_favorite_action_sends_message(self) -> None:
        app = SearchPanelApp()

        async with app.run_test() as pilot:
            panel = app.query_one(SearchPanel)
            list_view = app.query_one("#search-results", ListView)

            list_view.index = 0
            panel.focus()
            await pilot.pause()

            panel.action_favorite()
            await pilot.pause()

            assert len(app.favorite_records) == 1
            assert app.favorite_records[0].index == 0
