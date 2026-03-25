from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.mangadex.client import (
    ApiError,
    MangaDexApiClient,
    NotFoundError,
    RateLimitError,
)
from ..utils.session_manager import SessionManager
from ..widgets import SearchPanel


class SearchScreen(Screen):
    """
    The search screen of the application.

    Attributes:
        mangadex_client (MangaDexApiClient): The MangaDex API client to use for search queries.

    Reactive Attributes:
        results (list[tuple[str, str]]): A list of results for the current query. Each result is a tuple of (title, value)
    """

    results: reactive[list[tuple[str, str]]] = reactive([])

    def __init__(self) -> None:
        """Initialize the SearchScreen."""
        super().__init__()

        session_manager = SessionManager().create_session()
        self.mangadex_client = MangaDexApiClient(session_manager)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SearchPanel(debounce_duration=250).data_bind(
                results=SearchScreen.results
            )
            yield Footer()

    @work(exclusive=True)
    @on(SearchPanel.Search)
    async def _search(self, event: SearchPanel.Search) -> None:
        """Search for a query and display results."""
        query: str = event.query

        if not self.mangadex_client:
            self.log.error("MangaDex API client not initialized")
            return

        try:
            search_results = await self.mangadex_client.search_manga(query)
        except (NotFoundError, RateLimitError, ApiError) as e:
            self.log.error(f"Error searching for manga in SearchScreen: {e}")
            self.notify("Error searching for manga", severity="error")
            return

        new_results = [(item["title"], item["id"]) for item in search_results]
        self.results = new_results

    @on(SearchPanel.Selected)
    def _navigate_to_chapters(self, event: SearchPanel.Selected) -> None:
        """Navigate to the chapters screen for the selected result."""
        manga_id: str = event.value

        self.notify(f"Navigating to chapters screen for: {manga_id}")
