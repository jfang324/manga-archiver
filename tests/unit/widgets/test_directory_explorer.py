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
    def _record_directory_message(
        self, message: DirectoryExplorer.DirectoryChanged
    ) -> None:
        self.directory_records.append(message)


# Decorator to ignore errors produced by using Textual widgets directly in tests
@pytest.mark.filterwarnings("ignore::RuntimeWarning")
@pytest.mark.filterwarnings("ignore::pytest.PytestUnraisableExceptionWarning")
class TestFilteredDirectoryTree:
    def test_filters_hidden_directories(self):
        with TemporaryDirectory() as temp_dir:
            hidden_director: Path = Path(temp_dir) / ".hidden"
            visible_directory: Path = Path(temp_dir) / "visible"

            hidden_director.mkdir()
            visible_directory.mkdir()

            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths([hidden_director, visible_directory])

            assert len(result) == 1
            assert result[0] == visible_directory

    def test_filters_files(self):
        with TemporaryDirectory() as temp_dir:
            visible_files: Path = Path(temp_dir) / "file.txt"
            visible_directory: Path = Path(temp_dir) / "directory"

            visible_files.touch()
            visible_directory.mkdir()

            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths([visible_files, visible_directory])

            assert len(result) == 1
            assert result[0] == visible_directory

    def test_passes_through_normal_directories(self):
        with TemporaryDirectory() as temp_dir:
            visible_directory_1: Path = Path(temp_dir) / "dir1"
            visible_directory_2: Path = Path(temp_dir) / "dir2"

            visible_directory_1.mkdir()
            visible_directory_2.mkdir()

            tree: FilteredDirectoryTree = FilteredDirectoryTree(temp_dir)

            result: list[Path] = tree.filter_paths(
                [visible_directory_1, visible_directory_2]
            )

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

                directory_records: list[DirectoryExplorer.DirectoryChanged] = (
                    app.directory_records
                )
                assert len(directory_records) == 1

                message: DirectoryExplorer.DirectoryChanged = directory_records.pop()
                assert message.new_directory == str(child_directory)
