from textual.app import App

from .screens import MenuScreen, SearchScreen


class MangaDexDownloaderApp(App):
    """
    The core Textual application class for top level event handling.

    Attributes:

    Reactive Attributes:
    """

    DEFAULT_CSS = """
        MangaDexDownloaderApp {
            height: 100%;
            width: 100%;
        }
    """

    BINDINGS = [("escape", "safe_pop_screen", "Go back")]

    def on_mount(self) -> None:
        """On mount, install all screens and push the menu screen to the screen stack."""
        self.install_screen(MenuScreen(), name="menu_screen")
        self.install_screen(SearchScreen(), name="search_screen")

        self.push_screen("menu_screen")

    def action_safe_pop_screen(self) -> None:
        """Safely pop the screen."""
        if isinstance(self.screen_stack[-1], MenuScreen):
            return

        self.pop_screen()
