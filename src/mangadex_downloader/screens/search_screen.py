from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations import (
    ApiError,
    MangaDexApiClient,
    NotFoundError,
    RateLimitError,
)
from ..widgets import SearchPanel
from .selection_screen import SelectionScreen

if TYPE_CHECKING:
    from ..types import ProcessedManga

from ..utils import SessionManager


class SearchScreen(Screen):
    """
    The search screen of the application.

    Reactive Attributes:
        results (list[tuple[str, str]]): A list of results for the current query. Each result is a tuple of (title, manga_id)
    """

    results: reactive[list[tuple[str, str]]] = reactive([])

    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)

        self._session_manager = SessionManager().create_session()
        self._mangadex_client = MangaDexApiClient(self._session_manager)

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SearchPanel(debounce_duration=250).data_bind(
                results=SearchScreen.results
            )
            yield Footer()

    @work(exclusive=True)
    @on(SearchPanel.Search)
    async def _search_query(self, event: SearchPanel.Search) -> None:
        query: str = event.query

        if not self._mangadex_client:
            self.log.error("MangaDex API client not initialized")
            return

        try:
            search_results: list[
                ProcessedManga
            ] = await self._mangadex_client.search_manga(query)

        except RateLimitError:
            self.notify("Too many requests. Please wait a moment.", severity="error")
            return
        except (NotFoundError, ApiError):
            self.notify("Error searching for manga", severity="error")
            return

        new_results = [(item["title"], item["id"]) for item in search_results]
        self.results = new_results

    @on(SearchPanel.Selected)
    def _navigate_to_chapter_screen(self, event: SearchPanel.Selected) -> None:
        manga_title: str = event.title
        manga_id: str = event.value
        manga: ProcessedManga = {"title": manga_title, "id": manga_id}

        self.app.push_screen(SelectionScreen(manga))
