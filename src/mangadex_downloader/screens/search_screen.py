from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.screen import Screen
from textual.widgets import Footer

from ..widgets import SearchPanel


class SearchScreen(Screen):
    """The search screen of the application."""

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SearchPanel(debounce_duration=250)
            yield Footer()

    @work(exclusive=True)
    @on(SearchPanel.Search)
    async def _search(self, event: SearchPanel.Search) -> None:
        """Search for a query and display results."""
        query: str = event.query

        self.notify(f"Searching for: {query}")
