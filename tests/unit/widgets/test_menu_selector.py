from textual import on
from textual.app import App, ComposeResult
from textual.widgets import Label, ListView

from src.mangadex_downloader.constants.menu_options import MENU_OPTIONS
from src.mangadex_downloader.widgets.menu_selector import MenuSelector


class MenuSelectorApp(App):
    """Minimal App for testing MenuSelector."""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[MenuSelector.Selected] = []

    def compose(self) -> ComposeResult:
        yield MenuSelector(
            menu_options=MENU_OPTIONS,
            title="Menu Selector",
            description_title="Description",
        )

    @on(MenuSelector.Selected)
    def _record_navigation_message(self, message: MenuSelector.Selected) -> None:
        self.records.append(message)


class TestMenuSelector:
    async def test_navigating_menu_changes_description(self) -> None:
        app = MenuSelectorApp()

        async with app.run_test() as pilot:
            navigation_list: ListView = app.query_one("#navigation-list", ListView)
            menu_description: Label = app.query_one("#menu-description", Label)

            navigation_list.focus()

            starting_index = navigation_list.index
            assert starting_index is not None

            starting_description = menu_description.content
            assert starting_description == MENU_OPTIONS[starting_index].description

            await pilot.press("down")

            hovered_index = navigation_list.index
            assert hovered_index is not None
            assert hovered_index != starting_index

            new_description = menu_description.content
            assert new_description != starting_description
            assert new_description == MENU_OPTIONS[hovered_index].description

    async def test_selecting_menu_option_sends_message(self) -> None:
        app = MenuSelectorApp()

        async with app.run_test() as pilot:
            navigation_list: ListView = app.query_one("#navigation-list", ListView)

            navigation_list.focus()

            hovered_index = navigation_list.index
            assert hovered_index is not None

            await pilot.press("enter")

            messages = app.records
            assert len(messages) == 1
            assert messages[0].screen == MENU_OPTIONS[hovered_index].screen
