from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from textual import on
from textual.app import App, ComposeResult

from src.mangadex_downloader.widgets.directory_explorer import (
    DirectoryExplorer,
    FilteredDirectoryTree,
)


class DirectoryExplorerApp(App):
    def __init__(self):
        super().__init__()
        self.directory_records: list[DirectoryExplorer.DirectoryChanged] = []

    def compose(self) -> ComposeResult:
        yield DirectoryExplorer(title="Test")

    @on(DirectoryExplorer.DirectoryChanged)
    def _record_directory_message(self, message: DirectoryExplorer.DirectoryChanged) -> None:
        self.directory_records.append(message)


class TestFilteredDirectoryTree:
    def _create_item(self, parent_directory: Path, name: str, is_file: bool = False) -> Path:
        full_path: Path = parent_directory / name

        if is_file:
            full_path.touch()
        else:
            full_path.mkdir()

        return full_path

    def test_filters_hidden_directories(self):
        with TemporaryDirectory() as temp_dir:
            hidden_directory = self._create_item(Path(temp_dir), ".hidden")
            visible_directory = self._create_item(Path(temp_dir), "visible")
            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths([hidden_directory, visible_directory])

            assert len(result) == 1
            assert result[0] == visible_directory

    def test_filters_files(self):
        with TemporaryDirectory() as temp_dir:
            visible_file = self._create_item(Path(temp_dir), "visible.txt", True)
            hidden_file = self._create_item(Path(temp_dir), ".hidden.txt", True)
            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths([visible_file, hidden_file])

            assert len(result) == 0

    def test_passes_through_normal_directories(self):
        with TemporaryDirectory() as temp_dir:
            visible_directory_1 = self._create_item(Path(temp_dir), "1")
            visible_directory_2 = self._create_item(Path(temp_dir), "2")
            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths([visible_directory_1, visible_directory_2])

            assert len(result) == 2
            assert result[0] == visible_directory_1
            assert result[1] == visible_directory_2


@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
class TestDirectoryExplorer:
    async def test_navigating_down_tree_sends_message(self) -> None:
        app = DirectoryExplorerApp()

        async with app.run_test() as pilot:
            with TemporaryDirectory() as temp_dir:
                child_directory: Path = Path(temp_dir) / "test"

                child_directory.mkdir()

                directory_tree: FilteredDirectoryTree = app.query_one(
                    "#directory-tree", FilteredDirectoryTree
                )

                directory_tree.path = Path(temp_dir)
                await pilot.press("down")
                await pilot.press("enter")

                directory_records: list[DirectoryExplorer.DirectoryChanged] = app.directory_records
                assert len(directory_records) == 1

                message: DirectoryExplorer.DirectoryChanged = directory_records.pop()
                assert message.new_directory == str(child_directory)
