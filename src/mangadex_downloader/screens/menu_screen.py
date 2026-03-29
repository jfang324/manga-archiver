from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ..constants.menu_options import MENU_OPTIONS
from ..widgets import MenuSelector


class MenuScreen(Screen):
    """The main menu screen of the application.

    Displays a menu with options to search, view favorites, and access settings.
    """

    def compose(self) -> ComposeResult:
        with Vertical():
            yield MenuSelector(
                menu_options=MENU_OPTIONS,
                title="MangaDex Downloader",
                description_title="Description",
            )
            yield Footer()

    @on(MenuSelector.Selected)
    def _navigate_to_screen(self, event: MenuSelector.Selected) -> None:
        """Navigate to the specified screen."""
        available_screens: list[str] = [option.screen for option in MENU_OPTIONS]
        screen: str = event.screen

        if not screen or screen not in available_screens:
            self.log.error(f"Invalid screen selected in MenuScreen: {screen}")
            self.notify("Invalid screen selected", severity="error")
            return

        self.app.push_screen(screen)
