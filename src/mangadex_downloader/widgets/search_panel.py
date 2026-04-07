import asyncio
from asyncio import Task

from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Input, Label, ListItem, ListView


class SearchItem(ListItem):
    """A ListItem widget for displaying search results.

    Attributes:
        title (str): The title of the search result
    """

    DEFAULT_CSS = """
        SearchItem {
            height: auto;
        }

        Label {
            width: 1fr;
            text-wrap: wrap;
        }
    """

    def __init__(self, title: str, **kwargs) -> None:
        """Initialize the SearchItem widget.

        Args:
            title: The title of the search result
        """
        super().__init__(**kwargs)

        self.title = title

    def compose(self) -> ComposeResult:
        yield Label(self.title)


class SearchPanel(Widget):
    """A search panel widget for searching queries and displaying results.

    Attributes:
        debounce_duration (int): The duration in milliseconds to debounce the search query

    Reactive Attributes:
        results (list[tuple[str, str]]): A list of results for the current query. Each result is a tuple of (title, value)
    """

    DEFAULT_CSS = """
    SearchPanel {
        border: solid $primary;
        height: 1fr;
    }

    #search-section {
        width: 1fr;
        height: auto;
        border-bottom: solid $primary;
    }

    #search-label {
        padding: 0 1;
    }

    #results-section {
        width: 1fr;
        height: 1fr;
    }

    #results-header {
        width: 1fr;
        height: auto;
        padding: 0 1;
        border-bottom: solid $primary;
    }

    #results-label {
        width: 1fr;
        content-align: left middle;
    }

    #results-count {
        width: 1fr;
        content-align: right middle;
    }

    #search-results {
        height: 1fr;
        margin: 0 1;
    }
    """

    results: reactive[list[tuple[str, str]]] = reactive([])

    BINDINGS = [
        ("ctrl+f", "favorite", "Favorite"),
    ]

    class Search(Message):
        """Message to indicate that a search query has been made.

        Attributes:
            query (str): The search query
        """

        def __init__(self, query: str, **kwargs) -> None:
            """Initialize the Search message.

            Args:
                query: The search query
            """
            super().__init__(**kwargs)

            self.query = query

    class Selected(Message):
        """Message to indicate that a search result has been selected.

        Attributes:
            title (str): The title of the selected search result
            value (str): The value of the selected search result
        """

        def __init__(self, title: str, value: str, **kwargs) -> None:
            """Initialize the Selected message.

            Args:
                title: The title of the selected search result
                value: The value of the selected search result
            """
            super().__init__(**kwargs)

            self.title = title
            self.value = value

    class Favorite(Message):
        """Message to indicate that a search result should be favorited.

        Attributes:
            index (int): The index of the result to favorite
        """

        def __init__(self, index: int, **kwargs) -> None:
            """Initialize the Favorite message.

            Args:
                index: The index of the result to favorite
            """
            super().__init__(**kwargs)
            self.index = index

    def __init__(self, debounce_duration: int = 500, **kwargs) -> None:
        """Initialize the SearchPanel widget.

        Args:
            debounce_duration: The duration in milliseconds to debounce the search query. Defaults to 500
        """
        super().__init__(**kwargs)

        self._debounce_duration = debounce_duration
        self._debounce_task: Task | None = None  # Task to debounce the search query

    def compose(self) -> ComposeResult:
        with Vertical():
            with Vertical(id="search-section"):
                yield Label("Search", id="search-label")
                yield Input(id="search-input")

            with Vertical(id="results-section"):
                with Horizontal(id="results-header"):
                    yield Label("Results:", id="results-label")
                    yield Label(id="results-count")
                yield ListView(id="search-results")

    @on(Input.Changed, "#search-input")
    async def _debounced_search(self, event: Input.Changed) -> None:
        """Debounced search function to search for a query and display results."""
        if self._debounce_task:
            self._debounce_task.cancel()

        search_query: str = event.input.value
        self._debounce_task = asyncio.create_task(self._delayed_search_task(search_query))

    async def _delayed_search_task(self, search_query: str) -> None:
        """Function that delays posting the query message to the parent."""  # noqa: D401
        await asyncio.sleep(self._debounce_duration / 1000)

        self.post_message(self.Search(search_query))

    def _build_results(self, results: list[tuple[str, str]]) -> None:
        list_view: ListView = self.query_one("#search-results", ListView)
        list_items: list[ListItem] = [SearchItem(title) for title, _ in results]

        list_view.clear()
        list_view.extend(list_items)

    def watch_results(self, new_results: list[tuple[str, str]]) -> None:
        self._build_results(new_results)
        self.query_one("#results-count", Label).update(f"{len(new_results)} results")

    @on(ListView.Selected, "#search-results")
    def _select_result(self, event: ListView.Selected) -> None:
        index = event.index

        if index is None or index < 0 or index >= len(self.results):
            self.log.error("Invalid index selected in SearchPanel: %s", index)
            self.notify("Invalid index selected", severity="error")
            return

        title, value = self.results[index]
        self.post_message(self.Selected(title, value))

    def action_favorite(self) -> None:
        list_view = self.query_one("#search-results", ListView)
        index = list_view.index
        if index is not None and index >= 0:
            self.post_message(self.Favorite(index))
