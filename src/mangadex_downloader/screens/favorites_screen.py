from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..widgets import FavoritesPanel


class FavoritesScreen(Screen):
    """
    Favorites screen for displaying favorited manga.

    Reactive Attributes:
        favorites: List of favorited manga with manga_id and manga_title
    """

    favorites: reactive[list[dict[str, str]]] = reactive([])

    class Deleted(Message):
        """Message sent when a favorite manga is deleted."""

        def __init__(self, manga_id: str, manga_title: str, **kwargs) -> None:
            super().__init__(**kwargs)
            self.manga_id = manga_id
            self.manga_title = manga_title

    class Selected(Message):
        """Message sent when a favorite manga is selected."""

        def __init__(self, manga_id: str, manga_title: str, **kwargs) -> None:
            super().__init__(**kwargs)
            self.manga_id = manga_id
            self.manga_title = manga_title

    def compose(self) -> ComposeResult:
        yield FavoritesPanel().data_bind(favorites=FavoritesScreen.favorites)
        yield Footer()

    @on(FavoritesPanel.DeleteAt)
    def _on_delete_at(self, event: FavoritesPanel.DeleteAt) -> None:
        if event.index < 0 or event.index >= len(self.favorites):
            return
        fav = self.favorites[event.index]
        self.post_message(
            self.Deleted(manga_id=fav["manga_id"], manga_title=fav["manga_title"])
        )

    @on(FavoritesPanel.SelectAt)
    def _on_select_at(self, event: FavoritesPanel.SelectAt) -> None:
        if event.index < 0 or event.index >= len(self.favorites):
            return
        fav = self.favorites[event.index]
        self.post_message(
            self.Selected(manga_id=fav["manga_id"], manga_title=fav["manga_title"])
        )
