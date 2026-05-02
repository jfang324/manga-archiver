import asyncio
import logging
from contextlib import suppress

from tqdm import tqdm

from .constants.exit_codes import EXIT_RUNTIME_ERROR, EXIT_SUCCESS
from .pipeline_manager import PipelineManager
from .utils.benchmark_report import write_benchmark_report
from .workers.jobs import FetchingResourcesJob
from .workers.types import JobStatus

logger = logging.getLogger(__name__)

DEFAULT_HEADLESS_PROGRESS_POLL_INTERVAL_SECONDS = 0.25


class HeadlessPipelineRunner:
    """Run backlog jobs through the pipeline without launching the Textual app."""

    def __init__(
        self,
        pipeline_manager: PipelineManager,
        poll_interval_seconds: float = DEFAULT_HEADLESS_PROGRESS_POLL_INTERVAL_SECONDS,
    ) -> None:
        self._pipeline_manager = pipeline_manager
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

                    for job_id, (status, _) in self._pipeline_manager.get_jobs().items():
                        if status not in (JobStatus.COMPLETED, JobStatus.FAILED):
                            continue

                        if job_id in terminal_ids:
                            continue

                        terminal_ids.add(job_id)
                        progress.update(1)

                        if status == JobStatus.COMPLETED:
                            completed_ids.add(job_id)

                        if status == JobStatus.FAILED:
                            failed_ids.add(job_id)

                    await asyncio.sleep(self._poll_interval_seconds)

            print(
                f"Completed: {len(completed_ids)}, Failed: {len(failed_ids)}, "
                f"Skipped: {skipped_count}, Total: {len(jobs)}"
            )
            write_benchmark_report(self._pipeline_manager.get_benchmark_results())
            return EXIT_SUCCESS
        except Exception as e:
            logger.error("Runtime error during headless pipeline execution: %s", e)
            return EXIT_RUNTIME_ERROR
        finally:
            self._pipeline_manager.stop()
            pipeline_task.cancel()
            with suppress(asyncio.CancelledError, Exception):
                await pipeline_task
