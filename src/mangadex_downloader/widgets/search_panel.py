import asyncio
from asyncio import Task

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Input, Label, ListView


class SearchPanel(Widget):
    """
    A search panel widget for searching queries and displaying results.

    Attributes:
        debounce_duration (int): The duration in milliseconds to debounce the search query.

    Reactive Attributes:
        results (list[tuple[str, str]]): A list of results for the current query. Each result is a tuple of (title, value)
    """

    DEFAULT_CSS = """
    SearchPanel {
        border: solid $primary;
        height: 1fr;
    }

    #search-row {
        width: 1fr;
        height: auto;
        border-bottom: solid $primary;
    }

    #search-row > Label {
        padding: 0 1;
    }

    #results-row {
        width: 1fr;
        height: 1fr;
    }

    #results-row > Label {
        padding: 0 1;
        margin-bottom: 1;
    }

    #results-row > ListView {
        height: 1fr;
        margin: 0 1
    }
    """

    class Search(Message):
        """
        Message to indicate that a search query has been made.

        Attributes:
            query (str): The search query.
        """

        def __init__(self, query: str) -> None:
            """
            Initialize the Search message.

            Args:
                query (str): The search query.
            """
            super().__init__()

            self.query = query

    def __init__(self, debounce_duration: int = 500) -> None:
        """
        Initialize the SearchPanel widget.

        Args:
            debounce_duration (int): The duration in milliseconds to debounce the search query. Defaults to 500.
        """
        super().__init__()

        self.debounce_duration = debounce_duration
        self.debounce_task: Task | None = None  # Task to debounce the search query

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="search-row"):
                yield Label("Search")
                yield Input(id="search-input")

            with Vertical(id="results-row"):
                yield Label("Results")
                yield ListView(id="search-results")

    @on(Input.Changed, "#search-input")
    async def _debounced_search(self, event: Input.Changed) -> None:
        """Debounced search function to search for a query and display results."""
        if self.debounce_task:
            self.debounce_task.cancel()

        search_query: str = event.input.value
        self.debounce_task = asyncio.create_task(self._delayed_search(search_query))

    async def _delayed_search(self, search_query: str) -> None:
        """Function that delays posting the query message to the parent."""
        await asyncio.sleep(self.debounce_duration / 1000)

        self.post_message(self.Search(search_query))
