from textual.app import App, ComposeResult
from textual.containers import Horizontal

from .constants.menu_options import MENU_OPTIONS
from .widgets.menu_selector import MenuSelector


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

    def compose(self) -> ComposeResult:
        """Compose the application."""
        with Horizontal():
            yield MenuSelector(MENU_OPTIONS)
