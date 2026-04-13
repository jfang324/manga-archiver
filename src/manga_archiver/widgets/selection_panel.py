from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, SelectionList
from textual.widgets.selection_list import Selection


class SelectionPanel(Widget):
    """A selection panel widget for selecting a value from a list.

    Reactive Attributes:
        options (list[tuple[str, str, str]]): A list of options to display in the SelectionList. This format is (title, value, chapter) matching the ProcessedChapter type
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
        """Message to indicate that a selection has been made.

        Attributes:
            selected_pairs (list[tuple[str, str, float]]): A list of selected (name, id, chapter_number) tuples
        """

        def __init__(self, selected_pairs: list[tuple[str, str, float]], **kwargs) -> None:
            """Initialize the Selected message.

            Args:
                selected_pairs: A list of selected (name, id, chapter_number) tuples
            """
            super().__init__(**kwargs)

            self.selected_pairs = selected_pairs

    options: reactive[list[tuple[str, str, float]]] = reactive([])

    def __init__(self, title: str, **kwargs) -> None:
        """Initialize the SelectionPanel widget.

        Args:
            title: The title of the widget
        """
        super().__init__(**kwargs)

        self._title = title
        self._selected_values: list[str] = []

        # SelectionList only returns a list of values, so we need to map the values to their names
        self._name_map: dict[str, tuple[str, float]] = {}

    def compose(self) -> ComposeResult:
        with Vertical():
            yield Label(id="selection-label")
            yield SelectionList(id="selection-list")

    def _build_selection_options(self, options: list[tuple[str | None, str, float]]) -> None:
        selection_list: SelectionList = self.query_one("#selection-list", SelectionList)
        selection_items: list[Selection] = []

        for title, value, chapter in options:
            display_title = title if title else "untitled"
            name = f"{chapter:g}. {display_title}"

            self._name_map[value] = (display_title, chapter)
            selection_items.append(Selection(name, value))

        selection_list.clear_options()
        selection_list.add_options(selection_items)

    def watch_options(self, new_options: list[tuple[str | None, str, float]]) -> None:
        self.query_one("#selection-label", Label).update(f"{self._title} ({len(new_options)})")
        self._build_selection_options(new_options)

    @on(SelectionList.SelectedChanged, "#selection-list")
    def _update_selected_values(self, event: SelectionList.SelectedChanged) -> None:
        self._selected_values = event.selection_list.selected

    def action_request_download(self) -> None:
        name_and_id_pairs: list[tuple[str, str, float]] = []
        for value in self._selected_values:
            info = self._name_map.get(value)

            if not info:
                self.notify(f"Failed to find info for {value}", severity="error")
                return

            name_and_id_pairs.append((info[0], value, info[1]))

        self.post_message(self.Selected(name_and_id_pairs))

    def action_select_all(self) -> None:
        self.query_one("#selection-list", SelectionList).select_all()
