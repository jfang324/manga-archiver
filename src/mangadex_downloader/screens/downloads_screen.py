from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer, Label


class DownloadsScreen(Screen):
    """Downloads screen for the application."""

    DEFAULT_CSS = """
    DownloadsScreen {
        height: 1fr;
        border: solid $primary;
    }

    #placeholder {
        height: auto;
    }
    """

    def compose(self) -> ComposeResult:

        with Vertical(id="placeholder"):
            yield Label(content="Coming Soon")
        yield Footer()
