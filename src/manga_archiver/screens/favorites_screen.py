from textual import on
from textual.app import ComposeResult
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..repositories.types import FavoriteManga
from ..widgets import FavoritesPanel


class FavoritesScreen(Screen):
    """
    Favorites screen for displaying favorited manga.

    Reactive Attributes:
        favorites (list[FavoriteManga]): List of favorited manga with manga_id and manga_title
    """

    favorites: reactive[list[FavoriteManga]] = reactive([])

    class Deleted(Message):
        """Message sent when a favorite manga is deleted.

        Attributes:
            deleted_manga (FavoriteManga): The deleted manga
        """

        def __init__(self, deleted_manga: FavoriteManga, **kwargs) -> None:
            super().__init__(**kwargs)
            self.deleted_manga = deleted_manga

    class Selected(Message):
        """Message sent when a favorite manga is selected.

        Attributes:
            selected_manga (FavoriteManga): The selected manga
        """

        def __init__(self, selected_manga: FavoriteManga, **kwargs) -> None:
            super().__init__(**kwargs)
            self.selected_manga = selected_manga

    def compose(self) -> ComposeResult:
        yield FavoritesPanel().data_bind(favorites=FavoritesScreen.favorites)
        yield Footer()

    @on(FavoritesPanel.DeleteAt)
    def _on_delete_at(self, event: FavoritesPanel.DeleteAt) -> None:
        if event.index < 0 or event.index >= len(self.favorites):
            return

        deleted_manga = self.favorites[event.index]
        self.post_message(self.Deleted(deleted_manga))

    @on(FavoritesPanel.SelectAt)
    def _on_select_at(self, event: FavoritesPanel.SelectAt) -> None:
        if event.index < 0 or event.index >= len(self.favorites):
            return

        selected_manga = self.favorites[event.index]
        self.post_message(self.Selected(selected_manga))
