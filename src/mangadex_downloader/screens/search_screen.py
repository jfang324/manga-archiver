from typing import TYPE_CHECKING

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.content_providers import (
    MangaDexApiClient,
)
from ..integrations.exceptions import ApiError, NotFoundError, RateLimitError
from ..widgets import SearchPanel
from .selection_screen import SelectionScreen

if TYPE_CHECKING:
    from ..types import ProcessedManga


class SearchScreen(Screen):
    """
    The search screen of the application.

    Attributes:
        _mangadex_client: API client for MangaDex searches

    Reactive Attributes:
        results (list[tuple[str, str]]): A list of results for the current query. Each result is a tuple of (title, manga_id)
    """

    results: reactive[list[tuple[str, str]]] = reactive([])

    class FavoriteAdded(Message):
        """Message sent when a manga should be added to favorites."""

        def __init__(self, manga_id: str, manga_title: str, **kwargs) -> None:
            super().__init__(**kwargs)
            self.manga_id = manga_id
            self.manga_title = manga_title

    def __init__(self, mangadex_client: MangaDexApiClient, **kwargs) -> None:
        """
        Initialize the SearchScreen.

        Args:
            mangadex_client: The API client for MangaDex searches
        """
        super().__init__(**kwargs)

        self._mangadex_client = mangadex_client

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

        self.app.push_screen(SelectionScreen(manga, self._mangadex_client))

    @on(SearchPanel.Favorite)
    def _favorite_manga(self, event: SearchPanel.Favorite) -> None:
        index = event.index
        if index < 0 or index >= len(self.results):
            return

        title, manga_id = self.results[index]
        self.post_message(self.FavoriteAdded(manga_id=manga_id, manga_title=title))
