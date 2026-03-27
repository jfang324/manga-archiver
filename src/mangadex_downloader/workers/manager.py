import asyncio
from asyncio import Queue, Semaphore
from dataclasses import dataclass
from typing import Callable

from ..integrations.mangadex import MangaDexApiClient
from .base import WorkerConfig
from .jobs import FetchingResourcesJob, JobStatus
from .resolve_worker import ResolveWorker


@dataclass
class PipelineConfig:
    """
    A data container for the configuration of a pipeline.

    Attributes:
        num_resolve_workers (int): The number of resolve workers to use
        num_download_workers (int): The number of download workers to use
        num_merge_workers (int): The number of merge workers to use
    """

    num_resolve_workers: int = 1
    num_download_workers: int = 1
    num_merge_workers: int = 1

    resolve_rate_limit: int = 10


class PipelineManager:
    """
    A class that controls the processing pipeline, managing and configuring workers and queues.

    Attributes:
        mangadex_api_client (MangaDexApiClient): The API client for MangaDex
        on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
    """

    def __init__(
        self,
        mangadex_api_client: MangaDexApiClient,
        on_status_change: Callable[[str, JobStatus], None],
        config: PipelineConfig,
    ):
        """
        Initialize the pipeline manager.

        Args:
            mangadex_api_client (MangaDexApiClient): The API client for MangaDex
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (PipelineConfig): The configuration for the pipeline
        """
        self.resolve_queue: Queue = Queue()
        self.download_queue: Queue = Queue()

        self._resolve_semaphore: Semaphore = Semaphore(config.resolve_rate_limit)

        self.resolve_pool: list[ResolveWorker] = [
            ResolveWorker(
                api_client=mangadex_api_client,
                semaphore=self._resolve_semaphore,
                input_queue=self.resolve_queue,
                output_queue=self.download_queue,
                worker_id=f"resolve_worker_{index}",
                on_status_change=on_status_change,
                config=WorkerConfig(),
            )
            for index in range(config.num_resolve_workers)
        ]

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]):
        """Enqueue jobs to the resolve queue to start the pipeline."""
        for job in jobs:
            await self.resolve_queue.put(job)

    async def start(self):
        """
        Start all worker pools.
        """
        await asyncio.gather(*[w.run() for w in self.resolve_pool])

    async def stop(self):
        """
        Stop all worker pools.
        """
        for worker in self.resolve_pool:
            worker.stop()
