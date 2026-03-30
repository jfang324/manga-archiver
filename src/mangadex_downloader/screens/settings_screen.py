from textual.app import ComposeResult
from textual.screen import Screen
from textual.widgets import Footer

from ..widgets import SettingsPanel


class SettingsScreen(Screen):
    """Settings screen for the application."""

    def compose(self) -> ComposeResult:
        yield SettingsPanel()
        yield Footer()
