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

from typing import NamedTuple

from ..repositories import FavoriteManga


class SearchResult(NamedTuple):
    """A tuple containing the title and ID of a search result."""

    title: str
    id: str


class SearchScreen(Screen):
    """
    The search screen of the application.

    Reactive Attributes:
        results (list[SearchResult]): A list of results for the current query. Each result is a tuple of (title, manga_id)
    """

    results: reactive[list[SearchResult]] = reactive([])

    class FavoriteAdded(Message):
        """Message sent when a manga should be added to favorites.

        Attributes:
            favorited_manga (FavoriteManga): The favorited manga
        """

        def __init__(self, favorited_manga: FavoriteManga, **kwargs) -> None:
            super().__init__(**kwargs)
            self.favorited_manga = favorited_manga

    def __init__(self, mangadex_client: MangaDexApiClient, **kwargs) -> None:
        """Initialize the SearchScreen.

        Args:
            mangadex_client: The API client for MangaDex searches
        """
        super().__init__(**kwargs)

        self._mangadex_client = mangadex_client

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SearchPanel(debounce_duration=250).data_bind(results=SearchScreen.results)
            yield Footer()

    @work(exclusive=True)
    @on(SearchPanel.Search)
    async def _search_query(self, event: SearchPanel.Search) -> None:
        query: str = event.query

        try:
            search_results: list[ProcessedManga] = await self._mangadex_client.search_manga(query)

        except RateLimitError:
            self.notify("Too many requests. Please wait a moment.", severity="error")
            return
        except (NotFoundError, ApiError):
            self.notify("Error searching for manga", severity="error")
            return

        new_results = [SearchResult(item["title"], item["id"]) for item in search_results]
        self.results = new_results

    @on(SearchPanel.Selected)
    def _navigate_to_chapter_screen(self, event: SearchPanel.Selected) -> None:
        title, id = event.title, event.value  # noqa: A001
        manga: ProcessedManga = {"title": title, "id": id}

        self.app.push_screen(SelectionScreen(manga, self._mangadex_client))

    @on(SearchPanel.Favorite)
    def _favorite_manga(self, event: SearchPanel.Favorite) -> None:
        index = event.index
        if index < 0 or index >= len(self.results):
            return

        title, id = self.results[index]  # noqa: A001
        favorited_manga: FavoriteManga = {"manga_id": id, "manga_title": title}

        self.post_message(self.FavoriteAdded(favorited_manga))
