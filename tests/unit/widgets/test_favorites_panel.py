from textual import on
from textual.app import App, ComposeResult
from textual.reactive import reactive
from textual.widgets import Label, ListView

from src.mangadex_downloader.widgets.favorites_panel import FavoritesPanel


class FavoritesPanelApp(App):
    """Minimal App for testing FavoritesPanel."""

    mock_favorites: reactive[list[dict[str, str]]] = reactive(
        [
            {"manga_id": "1", "manga_title": "Title 1"},
            {"manga_id": "2", "manga_title": "Title 2"},
        ]
    )

    def __init__(self) -> None:
        super().__init__()
        self.delete_at_records: list[FavoritesPanel.DeleteAt] = []
        self.select_at_records: list[FavoritesPanel.SelectAt] = []

    def compose(self) -> ComposeResult:
        yield FavoritesPanel().data_bind(favorites=FavoritesPanelApp.mock_favorites)

    @on(FavoritesPanel.DeleteAt)
    def _record_delete_at_message(self, message: FavoritesPanel.DeleteAt) -> None:
        self.delete_at_records.append(message)

    @on(FavoritesPanel.SelectAt)
    def _record_select_at_message(self, message: FavoritesPanel.SelectAt) -> None:
        self.select_at_records.append(message)


class TestFavoritesPanel:
    async def test_favorites_list_displays_favorites(self) -> None:
        app = FavoritesPanelApp()

        async with app.run_test():
            favorites_list: ListView = app.query_one("#favorites-panel-list", ListView)

            assert len(favorites_list.children) == 2

            first_item = favorites_list.children[0]
            label = first_item.query_one(Label)
            assert "Title 1" in str(label.content)

            second_item = favorites_list.children[1]
            label = second_item.query_one(Label)
            assert "Title 2" in str(label.content)

    async def test_delete_action_sends_message(self) -> None:
        app = FavoritesPanelApp()

        async with app.run_test() as pilot:
            panel = app.query_one(FavoritesPanel)
            list_view = app.query_one("#favorites-panel-list", ListView)

            list_view.index = 0
            panel.focus()
            await pilot.pause()

            await pilot.press("ctrl+d")
            await pilot.pause()

            assert len(app.delete_at_records) == 1
            assert app.delete_at_records[0].index == 0

    async def test_select_action_sends_message(self) -> None:
        app = FavoritesPanelApp()

        async with app.run_test() as pilot:
            panel = app.query_one(FavoritesPanel)
            list_view = app.query_one("#favorites-panel-list", ListView)

            list_view.index = 1

            panel.action_select()
            await pilot.pause()

            assert len(app.select_at_records) == 1
            assert app.select_at_records[0].index == 1

    async def test_empty_favorites_displays_message(self) -> None:
        app = FavoritesPanelApp()
        app.mock_favorites = []

        async with app.run_test():
            favorites_list: ListView = app.query_one("#favorites-panel-list", ListView)

            assert len(favorites_list.children) == 1

            first_item = favorites_list.children[0]
            label = first_item.query_one(Label)
            assert "No favorites yet" in str(label.content)
