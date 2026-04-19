import logging
from typing import NamedTuple

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.content_providers import ContentProviderManager
from ..models import ContentSource
from ..repositories.types import FavoriteManga
from ..widgets import SearchPanel
from .selection_screen import SelectionScreen

logger = logging.getLogger(__name__)


class SearchResult(NamedTuple):
    """A tuple containing the title, ID, and source of a search result."""

    title: str
    id: str
    source: ContentSource


# The page size is 20 because this is the max value allowed by AllManga
PAGE_SIZE = 20


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
            search_results, errors = await self._provider_manager.search_manga(query, 1, PAGE_SIZE)
        except Exception as e:
            logger.error("Failed to search for manga: %s", e)
            self.notify("Failed to search for manga", severity="error")
            return

        if errors:
            logger.error("Errors returned from providers: %s", errors)
            self.notify(
                f"{len(errors)} provider(s) failed.",
                severity="warning",
            )

        new_results = [SearchResult(item.title, item.id, item.source) for item in search_results]
        self.results = new_results

    @on(SearchPanel.Selected)
    def _navigate_to_chapter_screen(self, event: SearchPanel.Selected) -> None:
        title, manga_id, source = event.title, event.value, event.source

        self.app.push_screen(SelectionScreen(manga_id, title, self._provider_manager, source))

    @on(SearchPanel.Favorite)
    def _favorite_manga(self, event: SearchPanel.Favorite) -> None:
        index = event.index
        if index < 0 or index >= len(self.results):
            logger.error("Index out of range: %s", index)
            return

        title, manga_id, source = self.results[index]
        favorited_manga = FavoriteManga(id=manga_id, title=title, source=source)

        self.post_message(self.FavoriteAdded(favorited_manga))

    @on(SearchPanel.Paginate)
    async def _retrieve_next_page(self, event: SearchPanel.Paginate) -> None:
        """Retrieve the next page of search results."""
        page = event.page

        try:
            search_results, errors = await self._provider_manager.search_manga(
                event.query, page, PAGE_SIZE
            )

        except Exception as e:
            logger.error("Failed to retrieve page %s: %s", page, e)
            self.notify("Failed to search for manga", severity="error")
            return

        if errors:
            self.notify(
                f"{len(errors)} provider(s) failed.",
                severity="warning",
            )

        new_page = [SearchResult(item.title, item.id, item.source) for item in search_results]

        if not new_page:
            return

        old_results = self.results
        new_results = old_results + new_page
        self.results = new_results

        # ListView rebuilds on results change, resetting index to 0.
        # Restore user's position to where they were before the rebuild.
        self.query_one(SearchPanel).select_index(len(old_results) - 1)
