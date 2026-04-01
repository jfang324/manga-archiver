from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView


class FavoritesPanel(Widget):
    """
    A panel widget for displaying and interacting with favorited manga.

    Reactive Attributes:
        favorites: List of favorited manga with manga_id and manga_title
    """

    DEFAULT_CSS = """
    FavoritesPanel {
        height: 1fr;
        border: solid $primary;
    }

    #favorites-panel-container {
        width: 1fr;
        height: 1fr;
    }

    #favorites-panel-header {
        width: 1fr;
        height: auto;
        border-bottom: solid $primary;
        padding: 0 1;
    }

    #favorites-panel-list {
        height: 1fr;
        padding: 0 1;
    }
    """

    favorites: reactive[list[dict[str, str]]] = reactive([])

    BINDINGS = [
        ("ctrl+d", "delete", "Delete favorite"),
    ]

    class DeleteAt(Message):
        """Message sent when delete action is triggered."""

        def __init__(self, index: int, **kwargs) -> None:
            super().__init__(**kwargs)
            self.index = index

    class SelectAt(Message):
        """Message sent when select action is triggered."""

        def __init__(self, index: int, **kwargs) -> None:
            super().__init__(**kwargs)
            self.index = index

    def compose(self) -> ComposeResult:
        with Vertical(id="favorites-panel-container"):
            yield Label("Favorites", id="favorites-panel-header")
            yield ListView(id="favorites-panel-list")

    def _build_favorites(self, favorites: list[dict[str, str]]) -> None:
        list_view: ListView = self.query_one("#favorites-panel-list", ListView)
        list_view.clear()

        if not favorites:
            list_view.append(
                ListItem(
                    Label(
                        "No favorites yet. Search for manga and press Ctrl+F to add favorites."
                    )
                )
            )
            return

        for fav in favorites:
            list_view.append(ListItem(Label(fav["manga_title"])))

    def watch_favorites(self, new_favorites: list[dict[str, str]]) -> None:
        self._build_favorites(new_favorites)

    def action_delete(self) -> None:
        list_view: ListView = self.query_one("#favorites-panel-list", ListView)
        index = list_view.index
        if index is not None and index >= 0:
            self.post_message(self.DeleteAt(index))

    @on(ListView.Selected)
    def _on_selected(self, event: ListView.Selected) -> None:
        list_view: ListView = event.list_view
        index = list_view.index
        if index is not None and index >= 0:
            self.post_message(self.SelectAt(index))
