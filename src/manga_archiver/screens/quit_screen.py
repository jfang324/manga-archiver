from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class QuitScreen(ModalScreen[bool]):
    """Quit screen showing a confirmation message."""

    DEFAULT_CSS = """
    QuitScreen {
        align: center middle;
    }

    #dialog {
        width: 40%;
        height: 40%;
        background: $surface;
        padding: 1 2;
    }

    #title {
        width: 1fr;
        content-align: center middle;
        text-style: bold;
        padding: 1 0;
    }

    #message {
        width: 1fr;
        content-align: center middle;
        padding: 0 1;
    }

    #buttons {
        align: center middle;
    }

    Button {
        width: 10;
        margin: 0 3;
    }
    """

    def __init__(self, incomplete_count: int = 0, **kwargs) -> None:
        """Initialize the QuitScreen.

        Args:
            incomplete_count: Number of jobs not yet in a terminal state
        """
        super().__init__(**kwargs)
        self._incomplete_count = incomplete_count

    def compose(self) -> ComposeResult:
        if self._incomplete_count > 0:
            message = (
                f"{self._incomplete_count} download{'s' if self._incomplete_count > 1 else ''} "
                f"{'are' if self._incomplete_count > 1 else 'is'} still in progress. "
                "Quitting will cancel them."
            )
        else:
            message = "Are you sure you want to quit?"

        with Vertical(id="dialog"):
            yield Label("Quit?", id="title")
            yield Label(message, id="message")

            with Horizontal(id="buttons"):
                yield Button("No", variant="primary", id="no")
                yield Button("Yes", variant="error", id="yes")

    @on(Button.Pressed, "#yes")
    def _request_quit(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def _cancel_quit(self) -> None:
        self.dismiss(False)
