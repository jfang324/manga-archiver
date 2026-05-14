import asyncio
import logging
from collections import defaultdict
from contextlib import suppress

from tqdm import tqdm

from .constants.exit_codes import EXIT_RUNTIME_ERROR, EXIT_SUCCESS
from .integrations.webhooks import WebhookClient
from .pipeline import PipelineManager
from .utils.benchmark_report import write_benchmark_report
from .workers.jobs import FetchingResourcesJob
from .workers.types import JobMetadata, JobStatus

logger = logging.getLogger(__name__)

DEFAULT_HEADLESS_PROGRESS_POLL_INTERVAL_SECONDS = 0.25
MAX_WEBHOOK_CHAPTER_LINES = 5


class HeadlessPipelineRunner:
    """Run backlog jobs through the pipeline without launching the Textual app."""

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        webhook_client: WebhookClient | None = None,
        poll_interval_seconds: float = DEFAULT_HEADLESS_PROGRESS_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._pipeline_manager = pipeline_manager
        self._webhook_client = webhook_client
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self, backlog: list[FetchingResourcesJob] | None) -> int:
        """Run backlog jobs through the pipeline."""
        jobs = backlog or []
        if not jobs:
            print("No missing chapters to process.")
            return EXIT_SUCCESS

        pipeline_task = asyncio.create_task(self._pipeline_manager.start())

        completed_ids: set[str] = set()
        failed_ids: set[str] = set()
        terminal_ids: set[str] = set()
        completed_metadata: list[JobMetadata] = []

        try:
            enqueue_result = await self._pipeline_manager.enqueue_jobs(jobs)
            accepted_count, skipped_count = (
                enqueue_result.accepted_count,
                enqueue_result.skipped_count,
            )

            with tqdm(total=accepted_count, desc="Processing backlog", unit="chapter") as progress:
                while len(terminal_ids) < accepted_count:
                    if pipeline_task.done():
                        exception = pipeline_task.exception()
                        if exception is not None:
                            raise exception

                    for job_id, (status, metadata) in self._pipeline_manager.get_jobs().items():
                        if status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                            continue

                        if job_id in terminal_ids:
                            continue

                        terminal_ids.add(job_id)
                        progress.update(1)

                        if status == JobStatus.COMPLETED:
                            completed_ids.add(job_id)
                            completed_metadata.append(metadata)

                        if status == JobStatus.FAILED:
                            failed_ids.add(job_id)

                    await asyncio.sleep(self._poll_interval_seconds)

            print(
                f"Completed: {len(completed_ids)}, Failed: {len(failed_ids)}, "
                f"Skipped: {skipped_count}, Total: {len(jobs)}"
            )
            if self._webhook_client is not None and completed_ids:
                try:
                    await self._webhook_client.notify(
                        _format_download_notification(completed_metadata)
                    )
                except Exception as e:
                    logger.error("Failed to send webhook notification: %s", e)
                    print("Warning: failed to send webhook notification.")

            write_benchmark_report(self._pipeline_manager.get_benchmark_results())
            return EXIT_SUCCESS
        except Exception as e:
            logger.error("Runtime error during headless pipeline execution: %s", e)
            return EXIT_RUNTIME_ERROR
        finally:
            self._pipeline_manager.stop()
            if not pipeline_task.done():
                pipeline_task.cancel()
            with suppress(asyncio.CancelledError):
                await pipeline_task


def _format_download_notification(completed_metadata: list[JobMetadata]) -> str:
    """Format downloaded chapter metadata for webhook notifications."""
    chapter_count = len(completed_metadata)
    chapter_label = "chapter" if chapter_count == 1 else "chapters"
    lines = [f"Downloaded {chapter_count} {chapter_label}:"]

    chapters_by_manga: dict[str, list[JobMetadata]] = defaultdict(list)
    for metadata in completed_metadata:
        chapters_by_manga[metadata.manga_title].append(metadata)

    sorted_metadata = sorted(
        (
            metadata
            for manga_chapters in chapters_by_manga.values()
            for metadata in sorted(
                manga_chapters,
                key=lambda chapter: (chapter.chapter_number, chapter.chapter_title.lower()),
            )
        ),
        key=lambda metadata: metadata.manga_title.lower(),
    )
    previous_manga_title = ""
    for metadata in sorted_metadata[:MAX_WEBHOOK_CHAPTER_LINES]:
        if metadata.manga_title != previous_manga_title:
            lines.append(f"\n{metadata.manga_title}:")
            previous_manga_title = metadata.manga_title

        lines.append(f"- Ch. {metadata.chapter_number:g} - {metadata.chapter_title}")

    remaining_count = chapter_count - MAX_WEBHOOK_CHAPTER_LINES
    if remaining_count > 0:
        lines.append(f"...and {remaining_count} more.")

    return "\n".join(lines)
