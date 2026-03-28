from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, SelectionList
from textual.widgets.selection_list import Selection


class SelectionPanel(Widget):
    """
    A selection panel widget for selecting a value from a list.

    Attributes:
        title (str): The title of the widget.
        selected_values (list[str, str]): A list of selected values in the format of ({chapter}. {title}, value)

    Reactive Attributes:
        options (list[tuple[str | None, str, str]]): A list of options to display in the SelectionList. This format is (title, value, chapter) matching the ProcessedChapter type.
    """

    DEFAULT_CSS = """
    SelectionPanel {
        border: solid $primary;
        height: 1fr;
    }

    #selection-label {
        width: 1fr;
        height: auto;
        border-bottom: solid $primary;
        padding: 0 1;
    }

    #selection-list {
        height: 1fr;
    }
    """

    BINDINGS = [
        ("ctrl+s", "request_download", "Download chapters"),
        ("ctrl+a", "select_all", "Select all"),
    ]

    class Selected(Message):
        """
        Message to indicate that a selection has been made.

        Attributes:
            selected_pairs (list[tuple[str, str]]): A list of selected (name, value) pairs.
        """

        def __init__(self, selected_pairs: list[tuple[str, str]]) -> None:
            """
            Initialize the Selected message.

            Args:
                selected_pairs (list[tuple[str, str]]): A list of selected (name, value) pairs.
            """
            super().__init__()

            self.selected_pairs = selected_pairs

    options: reactive[list[tuple[str | None, str, str]]] = reactive([])

    def __init__(self, title: str) -> None:
        """
        Initialize the SelectionPanel widget.

        Args:
            title (str): The title of the widget.
        """
        super().__init__()

        self.title = title
        self.selected_values: list[str] = []

        # SelectionList only returns a list of values, so we need to map the values to their names
        self.name_map: dict[str, str] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(id="selection-label")
            yield SelectionList(id="selection-list")

    def _build_selection_options(
        self, options: list[tuple[str | None, str, str]]
    ) -> None:
        """Build the options list for the SelectionList."""
        selection_list: SelectionList = self.query_one("#selection-list", SelectionList)
        selection_items: list[Selection] = []

        for title, value, chapter in options:
            name = f"{chapter}. {title or ''}"

            self.name_map[value] = name
            selection_items.append(Selection(name, value))

        selection_list.clear_options()
        selection_list.add_options(selection_items)

    def watch_options(self, new_options: list[tuple[str | None, str, str]]) -> None:
        """Watch for changes to the options list and update the SelectionList."""
        self.query_one("#selection-label", Label).update(
            f"{self.title} ({len(new_options)})"
        )
        self._build_selection_options(new_options)

    @on(SelectionList.SelectedChanged, "#selection-list")
    def _update_selected_values(self, event: SelectionList.SelectedChanged) -> None:
        """Update the selected values when an option is selected."""
        self.selected_values = event.selection_list.selected

    def action_request_download(self) -> None:
        """Request downloads be queued for the selected values."""
        name_and_id_pairs: list[tuple[str, str]] = [
            (self.name_map.get(value, ""), value) for value in self.selected_values
        ]

        self.post_message(self.Selected(name_and_id_pairs))

    def action_select_all(self) -> None:
        """Select all options."""
        self.query_one("#selection-list", SelectionList).select_all()
