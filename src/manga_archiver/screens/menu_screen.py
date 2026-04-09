from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ..constants import MENU_OPTIONS
from ..widgets import MenuSelector


class MenuScreen(Screen):
    """The main menu screen of the application."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield MenuSelector(
                menu_options=MENU_OPTIONS,
                title="Manga Archiver",
                description_title="Description",
            )
            yield Footer()

    @on(MenuSelector.Selected)
    def _navigate_to_screen(self, event: MenuSelector.Selected) -> None:
        available_screens: list[str] = [option.screen for option in MENU_OPTIONS]
        requested_screen: str = event.screen

        if not requested_screen or requested_screen not in available_screens:
            self.log.error("Invalid screen selected in MenuScreen: %s", requested_screen)
            self.notify("Invalid screen selected", severity="error")

            return

        self.app.push_screen(requested_screen)
