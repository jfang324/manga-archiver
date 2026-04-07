from textual import on
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView

from ..constants import MenuOption


class MenuSelector(Widget):
    """A Menu widget for selecting a screen to display.

    Attributes:
        options (list[MenuOption]): List of MenuOption objects to display
        title (str): Title of the widget
        description_title (str): Title of the description column
    """

    DEFAULT_CSS = """
    MenuSelector {
        border: solid $primary;
        height: 1fr;
    }

    Vertical {
        padding: 0 1;
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
        """Message to indicate that a MenuOption has been selected.

        Attributes:
            screen (str): The screen to display when the option is selected
        """

        def __init__(self, screen: str, **kwargs) -> None:
            """
            Initialize the Selected message.

            Args:
                screen: The screen to display when the option is selected
            """
            super().__init__(**kwargs)

            self.screen = screen

    def __init__(
        self,
        menu_options: list[MenuOption],
        title: str,
        description_title: str,
        **kwargs,
    ) -> None:
        """Initialize the MenuSelector widget.

        Args:
            menu_options: List of MenuOption objects to display
            title: Title of the widget
            description_title: Title of the description column
        """
        super().__init__(**kwargs)

        self._menu_options = menu_options or []
        self._title = title
        self._description_title = description_title

    def compose(self) -> ComposeResult:
        with Horizontal():
            with Vertical(id="navigation-column"):
                yield Label(f"{self._title} 📖", id="navigation-label")
                yield ListView(
                    *[
                        ListItem(Label(option.display_name))
                        for option in self._menu_options
                    ],
                    id="navigation-list",
                )

            with Vertical(id="description-column"):
                yield Label(f"{self._description_title}", id="description-label")
                yield Label(
                    self._menu_options[0].description if self._menu_options else "",
                    id="menu-description",
                )

    @on(ListView.Highlighted, "#navigation-list")
    def _update_description_column(self, event: ListView.Highlighted) -> None:
        list_view: ListView = event.list_view

        if list_view.index is not None:
            self._build_description_column(list_view.index)

    def _build_description_column(self, index: int) -> None:
        if not self._menu_options:
            return

        if index < 0 or index >= len(self._menu_options):
            self.log.error("Invalid index selected in MenuSelector: %s", index)
            self.notify("Invalid index selected", severity="error")
            return

        description_label: Label = self.query_one("#description-label", Label)
        menu_description: Label = self.query_one("#menu-description", Label)

        description_label.update("Description")
        menu_description.update(self._menu_options[index].description)

    @on(ListView.Selected, "#navigation-list")
    def _request_screen_change(self, event: ListView.Selected) -> None:
        requested_screen: str = self._menu_options[event.index].screen

        self.post_message(self.Selected(requested_screen))
