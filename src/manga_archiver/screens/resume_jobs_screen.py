from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Label


class ResumeJobsScreen(ModalScreen[bool]):
    """Prompt users to resume jobs from a previous session."""

    DEFAULT_CSS = """
    ResumeJobsScreen {
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

    def __init__(self, resumable_count: int, **kwargs) -> None:
        """Initialize the resume jobs prompt.

        Args:
            resumable_count: Number of jobs that can be resumed.
        """
        super().__init__(**kwargs)
        self._resumable_count = resumable_count

    def compose(self) -> ComposeResult:
        job_label = "job" if self._resumable_count == 1 else "jobs"
        message = (
            f"Found {self._resumable_count} resumable {job_label} "
            "from a previous session. Resume them?"
        )

        with Vertical(id="dialog"):
            yield Label("Resume downloads?", id="title")
            yield Label(message, id="message")

            with Horizontal(id="buttons"):
                yield Button("No", variant="primary", id="no")
                yield Button("Yes", variant="success", id="yes")

    @on(Button.Pressed, "#yes")
    def _resume_jobs(self) -> None:
        self.dismiss(True)

    @on(Button.Pressed, "#no")
    def _discard_jobs(self) -> None:
        self.dismiss(False)
