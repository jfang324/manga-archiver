from typing import NamedTuple, TypedDict

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.screen import Screen
from textual.widgets import Footer

from ..integrations.content_providers import ContentProviderManager
from ..integrations.exceptions import ApiError, NotFoundError, RateLimitError
from ..models import Chapter, ContentSource
from ..widgets import SelectionPanel


class ChapterResult(NamedTuple):
    """A tuple containing the title, ID, and chapter number of a chapter."""

    title: str
    id: str
    chapter: float


class PartialJob(TypedDict):
    """A dictionary containing partial information for a job."""

    manga_title: str
    chapter_id: str
    chapter_number: float
    chapter_title: str
    source: ContentSource


class SelectionScreen(Screen):
    """The selection screen of the application.

    Reactive Attributes:
        results (list[ChapterResult]): A list of chapters for the selected manga.
    """

    class EnqueueJobs(Message):
        """Message to enqueue jobs to the pipeline.

        Attributes:
            partial_jobs (list[PartialJob]): partial information for jobs to enqueue
        """

        def __init__(self, partial_jobs: list[PartialJob], **kwargs) -> None:
            super().__init__(**kwargs)

            self.partial_jobs = partial_jobs

    results: reactive[list[ChapterResult]] = reactive([])

    def __init__(
        self,
        manga_id: str,
        manga_title: str,
        provider_manager: ContentProviderManager,
        source: ContentSource = ContentSource.MANGADEX,
        **kwargs,
    ) -> None:
        """Initialize the SelectionScreen.

        Args:
            manga_id: The ID of the manga
            manga_title: The title of the manga
            provider_manager: The content provider manager
            source: The content source (defaults to MANGADEX)
        """
        super().__init__(**kwargs)

        self._provider_manager = provider_manager
        self._source = source
        self._manga_id = manga_id
        self._manga_title = manga_title

    @work
    async def on_mount(self) -> None:
        """On mount, fetch the chapters for the selected manga."""
        try:
            chapters: list[Chapter] = await self._provider_manager.get_chapters(
                self._source, self._manga_id
            )
        except RateLimitError:
            self.notify("Too many requests. Please wait a moment.", severity="error")
            return
        except (NotFoundError, ApiError):
            self.notify("Error fetching chapters", severity="error")
            return

        new_results: list[ChapterResult] = [
            ChapterResult(
                chapter.title or "untitled",
                chapter.id,
                chapter.chapter_num,
            )
            for chapter in chapters
        ]

        self.results = new_results

    def compose(self) -> ComposeResult:
        with Vertical():
            yield SelectionPanel(self._manga_title, self._source).data_bind(
                options=SelectionScreen.results
            )
            yield Footer()

    def _queue_downloads(self, selected_chapters: list[tuple[str, str, float]]) -> None:
        partial_jobs: list[PartialJob] = [
            PartialJob(
                manga_title=self._manga_title,
                chapter_id=chapter_id,
                chapter_number=chapter_number,
                chapter_title=chapter_title,
                source=self._source,
            )
            for chapter_title, chapter_id, chapter_number in selected_chapters
        ]

        self.post_message(self.EnqueueJobs(partial_jobs))
        self.notify(f"Queued {len(selected_chapters)} downloads for {self._manga_title}")

    @on(SelectionPanel.Selected)
    def _navigate_to_menu_screen(self, event: SelectionPanel.Selected) -> None:
        selected_chapters: list[tuple[str, str, float]] = event.selected_pairs

        self._queue_downloads(selected_chapters)

        # pop screen twice to get back to the menu screen
        self.app.pop_screen()
        self.app.pop_screen()
