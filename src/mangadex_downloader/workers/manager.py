import asyncio
import logging
import tracemalloc
from asyncio import Queue, Semaphore
from dataclasses import dataclass
from typing import Callable

from ..integrations.mangadex import MangaDexApiClient
from ..utils.downloader import DownloadClient
from ..utils.pdf_generator import PdfGenerator
from .base import WorkerConfig
from .benchmark_worker import BenchmarkWorker
from .download_worker import DownloadWorker
from .jobs import (
    BenchmarkJob,
    DownloadingJob,
    FetchingResourcesJob,
    JobStatus,
    MergingJob,
)
from .merge_worker import MergeWorker
from .resolve_worker import ResolveWorker


@dataclass
class PipelineConfig:
    """
    A data container for the configuration of a pipeline.

    Attributes:
        num_resolve_workers (int): The number of resolve workers to use
        num_download_workers (int): The number of download workers to use
        num_merge_workers (int): The number of merge workers to use
        resolve_rate_limit (int): The global rate limit for resolve workers (requests per second)
        download_rate_limit (int): The global rate limit for download workers (requests per second)
        benchmark_enabled (bool): Whether to enable benchmark worker for timing
        benchmark_expected_count (int): Number of jobs expected in benchmark
    """

    num_resolve_workers: int = 1
    num_download_workers: int = 1
    num_merge_workers: int = 1

    resolve_rate_limit: int = 10
    download_rate_limit: int = 10

    benchmark_enabled: bool = False
    benchmark_expected_count: int | None = None


class PipelineManager:
    """
    A class that controls the processing pipeline, managing and configuring workers and queues.

    Attributes:
        mangadex_api_client (MangaDexApiClient): The API client for MangaDex
        download_client (DownloadClient): The client for downloading images
        on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
        config (PipelineConfig): The configuration for the pipeline
    """

    def __init__(
        self,
        mangadex_api_client: MangaDexApiClient,
        download_client: DownloadClient,
        on_status_change: Callable[[str, JobStatus], None],
        config: PipelineConfig,
        benchmark_callback: Callable[[float, float], None] | None = None,
    ):
        """
        Initialize the pipeline manager.

        Args:
            mangadex_api_client (MangaDexApiClient): The API client for MangaDex
            download_client (DownloadClient): The client for downloading images
            on_status_change (Callable[[str, JobStatus], None]): The callback function for progress updates
            config (PipelineConfig): The configuration for the pipeline
            benchmark_callback (Callable[[float, float], None]): Optional callback for benchmark results
        """
        self.resolve_queue: Queue[FetchingResourcesJob] = Queue()
        self.download_queue: Queue[DownloadingJob] = Queue()
        self.merge_queue: Queue[MergingJob] = Queue()
        self.benchmark_queue: Queue[BenchmarkJob] = Queue()

        self._resolve_semaphore: Semaphore = Semaphore(config.resolve_rate_limit)
        self._download_semaphore: Semaphore = Semaphore(config.download_rate_limit)

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
        self.download_pool: list[DownloadWorker] = [
            DownloadWorker(
                download_client=download_client,
                semaphore=self._download_semaphore,
                input_queue=self.download_queue,
                output_queue=self.merge_queue,
                worker_id=f"download_worker_{index}",
                on_status_change=on_status_change,
                config=WorkerConfig(),
            )
            for index in range(config.num_download_workers)
        ]
        self.merge_pool: list[MergeWorker] = [
            MergeWorker(
                pdf_generator=PdfGenerator(),
                input_queue=self.merge_queue,
                output_queue=self.benchmark_queue if config.benchmark_enabled else None,
                worker_id=f"merge_worker_{index}",
                on_status_change=on_status_change,
                config=WorkerConfig(),
            )
            for index in range(config.num_merge_workers)
        ]

        self.benchmark_pool: list[BenchmarkWorker] = []
        self._track_memory = config.benchmark_enabled
        self._benchmark_callback = benchmark_callback

        if config.benchmark_enabled:
            wrapped_callback = self._wrap_benchmark_callback(benchmark_callback)
            self.benchmark_pool = [
                BenchmarkWorker(
                    expected_count=config.benchmark_expected_count,
                    benchmark_callback=wrapped_callback,
                    input_queue=self.benchmark_queue,
                    output_queue=None,
                    worker_id=f"benchmark_worker_{index}",
                    on_status_change=on_status_change,
                    config=WorkerConfig(),
                )
                for index in range(1)
            ]

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]):
        """Enqueue jobs to the resolve queue to start the pipeline."""
        for job in jobs:
            await self.resolve_queue.put(job)

    def _wrap_benchmark_callback(
        self, original_callback: Callable[[float, float], None] | None
    ) -> Callable[[float, float], None]:
        """Wrap benchmark callback to include memory logging."""

        def wrapped_callback(earliest_start: float, latest_end: float) -> None:
            if self._track_memory:
                _, peak = tracemalloc.get_traced_memory()
                peak_mb = peak / 1024 / 1024
                logging.debug(
                    f"Benchmark: time={(latest_end - earliest_start) / 1_000_000:.2f}ms, "
                    f"peak_memory={peak_mb:.2f}MB"
                )

            if original_callback:
                original_callback(earliest_start, latest_end)

        return wrapped_callback

    async def start(self):
        """
        Start all worker pools.
        """
        if self._track_memory:
            tracemalloc.start()

        all_workers = (
            self.resolve_pool
            + self.download_pool
            + self.merge_pool
            + self.benchmark_pool
        )

        await asyncio.gather(*[w.run() for w in all_workers])

    async def stop(self):
        """
        Stop all worker pools.
        """
        for worker in self.resolve_pool:
            worker.stop()
