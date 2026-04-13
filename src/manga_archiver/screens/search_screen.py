from typing import NamedTuple

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.content_providers import ContentProviderManager
from ..integrations.exceptions import ApiError, NotFoundError, RateLimitError
from ..repositories import FavoriteManga
from ..widgets import SearchPanel
from .selection_screen import SelectionScreen


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

    def __init__(self, provider_manager: ContentProviderManager, **kwargs) -> None:
        """Initialize the SearchScreen.

        Args:
            provider_manager: The content provider manager for searches
        """
        super().__init__(**kwargs)

        self._provider_manager = provider_manager

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SearchPanel(debounce_duration=250).data_bind(results=SearchScreen.results)
            yield Footer()

    @work(exclusive=True)
    @on(SearchPanel.Search)
    async def _search_query(self, event: SearchPanel.Search) -> None:
        query: str = event.query

        try:
            search_results, errors = await self._provider_manager.search_manga(query)

        except RateLimitError:
            self.notify("Too many requests. Please wait a moment.", severity="error")
            return
        except (NotFoundError, ApiError):
            self.notify("Error searching for manga", severity="error")
            return

        if errors:
            self.notify(
                f"{len(errors)} provider(s) failed.",
                severity="warning",
            )

        new_results = [SearchResult(item.title, item.id) for item in search_results]
        self.results = new_results

    @on(SearchPanel.Selected)
    def _navigate_to_chapter_screen(self, event: SearchPanel.Selected) -> None:
        title, manga_id = event.title, event.value

        self.app.push_screen(SelectionScreen(manga_id, title, self._provider_manager))

    @on(SearchPanel.Favorite)
    def _favorite_manga(self, event: SearchPanel.Favorite) -> None:
        index = event.index
        if index < 0 or index >= len(self.results):
            return

        title, manga_id = self.results[index]
        favorited_manga: FavoriteManga = {"manga_id": manga_id, "manga_title": title}

        self.post_message(self.FavoriteAdded(favorited_manga))
