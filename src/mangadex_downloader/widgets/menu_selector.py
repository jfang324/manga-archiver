from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..constants.menu_options import MenuOption


class MenuSelector(Widget):
    """
    A Menu widget for selecting a screen to display.

    Attributes:
        options (list[MenuOption]): List of MenuOption objects to display.
    """

    DEFAULT_CSS = """
    MenuSelector {
        border: solid $primary;
        height: 1fr;
    }

    Vertical {
        padding-left: 1;
        padding-right: 1;
    }

    #navigation-column {
        width: 1fr;
        border-right: solid $primary;
    }

    #navigation-label {
        text-align: center;
        border-bottom: solid $primary;
        width: 1fr;
    }

    #navigation-list {
        background: $primary 0%;
    }

    #description-column {
        width: 2fr;
    }

    #description-label {
        text-align: center;
        border-bottom: solid $primary;
        width: 1fr;
    }
    """

    class Selected(Message):
        """
        Message to indicate that a MenuOption has been selected.

        Attributes:
            screen (str): The screen to display when the option is selected.
        """

        def __init__(self, screen: str) -> None:
            super().__init__()
            self.screen = screen

    def __init__(self, menu_options: list[MenuOption], **kwargs) -> None:
        super().__init__(**kwargs)
        self.menu_options = menu_options or []

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="navigation-column"):
                yield Label("MangaDex Downloader 📖", id="navigation-label")
                yield ListView(
                    *[ListItem(Label(opt.display_name)) for opt in self.menu_options],
                    id="navigation-list",
                )

            with Vertical(id="description-column"):
                yield Label("Description", id="description-label")
                yield Label(
                    self.menu_options[0].description if self.menu_options else "",
                    id="menu-description",
                )

    def on_list_view_highlighted(self) -> None:
        """Update the description column when an option is highlighted."""
        list_view: ListView = self.query_one("#navigation-list", ListView)

        if list_view.index is not None:
            self._build_description_column(list_view.index)

    def _build_description_column(self, index: int) -> None:
        """Populate the description column with the description for the highlighted MenuOption."""
        if not self.menu_options:
            return
        if index < 0 or index >= len(self.menu_options):
            self.notify("Invalid index selected", severity="error")
            self.log.error(f"Invalid index selected in MenuSelector: {index}")
            return

        description_label: Label = self.query_one("#description-label", Label)
        menu_description: Label = self.query_one("#menu-description", Label)

        description_label.update("Description")
        menu_description.update(self.menu_options[index].description)

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        """Send a Selected message to the parent to signal a screen change."""
        requested_screen: str = self.menu_options[event.index].screen

        self.post_message(self.Selected(requested_screen))
