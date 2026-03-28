from typing import TypedDict

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.mangadex.client import (
    ApiError,
    MangaDexApiClient,
    NotFoundError,
    RateLimitError,
)
from ..types import ProcessedChapter, ProcessedManga
from ..utils.session_manager import SessionManager
from ..widgets import SelectionPanel


class PartialJob(TypedDict):
    manga_title: str
    chapter_id: str
    chapter_title: str


class SelectionScreen(Screen):
    """
    The selection screen of the application.

    Attributes:
        mangadex_client (MangaDexApiClient): The MangaDex API client to use for chapter retrieval.
        manga (ProcessedManga): The selected manga.

    Reactive Attributes:
        results (list[tuple[str | None, str, str]]): A list of chapters for the selected manga. Each result is a tuple of (title, chapter_id, chapter_number)
    """

    class EnqueueJobs(Message):
        """
        Message to enqueue jobs to the pipeline.

        Attributes:
            partial_jobs (list[PartialJob]): The jobs to enqueue.
        """

        def __init__(self, partial_jobs: list[PartialJob]) -> None:
            """
            Initialize the EnqueueJobs message.

            Args:
                partial_jobs (list[PartialJob]): The jobs to enqueue.
            """
            super().__init__()

            self.partial_jobs = partial_jobs

    results: reactive[list[tuple[str | None, str, str]]] = reactive([])

    def __init__(self, manga: ProcessedManga) -> None:
        """
        Initialize the SelectionScreen.

        Args:
            manga (ProcessedManga): The selected manga.
        """
        super().__init__()

        session_manager = SessionManager().create_session()
        self.mangadex_client = MangaDexApiClient(session_manager)

        self.manga_id = manga["id"]
        self.manga_title = manga["title"]

    @work
    async def on_mount(self) -> None:
        """On mount, fetch the chapters for the selected manga."""
        try:
            chapters: list[ProcessedChapter] = await self.mangadex_client.get_chapters(
                self.manga_id
            )
        except (NotFoundError, RateLimitError, ApiError) as e:
            self.log.error(f"Error fetching chapters for SelectionScreen: {e}")
            self.notify("Error fetching chapters", severity="error")
            return

        new_results: list[tuple[str | None, str, str]] = [
            (chapter["title"], chapter["id"], chapter["chapter"])
            for chapter in chapters
        ]

        self.results = new_results

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SelectionPanel(self.manga_title).data_bind(
                options=SelectionScreen.results
            )
            yield Footer()

    def _queue_downloads(self, selected_chapters: list[tuple[str, str]]) -> None:
        """Queue downloads for the selected chapters."""
        partial_jobs: list[PartialJob] = [
            {
                "manga_title": self.manga_title,
                "chapter_id": chapter_id,
                "chapter_title": chapter_title,
            }
            for chapter_title, chapter_id in selected_chapters
        ]

        self.post_message(self.EnqueueJobs(partial_jobs))
        self.notify(f"Queued {len(selected_chapters)} downloads for {self.manga_title}")

    @on(SelectionPanel.Selected)
    def _navigate_to_menu_screen(self, event: SelectionPanel.Selected) -> None:
        """Navigate to the menu screen."""
        selected_chapters: list[tuple[str, str]] = event.selected_pairs

        self._queue_downloads(selected_chapters)

        # pop screen twice to get back to the menu screen
        self.app.pop_screen()
        self.app.pop_screen()
