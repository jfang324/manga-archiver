from collections.abc import Iterable
from pathlib import Path

from textual import events, on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import DirectoryTree


class FilteredDirectoryTree(DirectoryTree):
    """A custom DirectoryTree widget that filters out files and hidden directories"""  # noqa: D415

    def filter_paths(self, paths: Iterable[Path]) -> list[Path]:
        return [p for p in paths if not p.name.startswith(".") and p.is_dir()]


class DirectoryExplorer(Widget):
    """A DirectoryExplorer widget that allows the user to navigate through directories and select files.

    Reactive Attributes:
        current_directory (str): The directory path that will act as the root of the directory explorer
    """

    DEFAULT_CSS = """
        DirectoryExplorer {
            border: solid $primary;
            height: 1fr;
        }

        DirectoryExplorer DirectoryTree {
            margin: 0 1;
        }
    """

    current_directory: reactive[str] = reactive(".")

    class DirectoryChanged(Message):
        """Message to indicate that the current directory has changed

        Attributes:
            new_directory (str): The path of the new root directory
            control (Widget): A reference to the DirectoryExplorer widget
        """  # noqa: D415

        @property
        def control(self) -> Widget:
            """Required for @on decorator selector matching"""  # noqa: D415
            return self._control

        def __init__(self, new_directory: str, control: Widget, **kwargs) -> None:
            """
            Initializes the DirectoryChanged message

            Args:
                new_directory: The path of the new root directory
                control: A reference to the DirectoryExplorer widget
            """  # noqa: D401, D415
            super().__init__(**kwargs)

            self.new_directory = new_directory
            self._control = control

    def __init__(self, title: str, **kwargs) -> None:
        """Initialize the DirectoryExplorer.

        Args:
            title: The title to display on the directory explorer's border
        """
        super().__init__(**kwargs)

        self.border_title = title

    def compose(self) -> ComposeResult:
        with Vertical():
            yield FilteredDirectoryTree(self.current_directory, id="directory-tree")

    def _reload_directory_tree(self, new_directory: str) -> None:
        self.border_subtitle = new_directory

        if self._is_mounted:
            directory_tree = self.query_one("#directory-tree", FilteredDirectoryTree)

            directory_tree.path = new_directory
            directory_tree.root.collapse()

    def watch_current_directory(self) -> None:
        self._reload_directory_tree(self.current_directory)

    @on(DirectoryTree.DirectorySelected)
    def _signal_navigate_to_child_directory(self, event: DirectoryTree.DirectorySelected) -> None:
        new_directory = str(event.path)

        self.post_message(self.DirectoryChanged(new_directory, self))

    @on(events.Key)
    def _signal_navigate_to_parent_directory(self, event: events.Key) -> None:
        if event.key != "escape":
            return

        event.stop()
        parent = Path(self.current_directory).parent

        if parent != Path(self.current_directory):
            self.post_message(self.DirectoryChanged(str(parent), self))
