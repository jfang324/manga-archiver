import asyncio
import logging
import tracemalloc
from asyncio import Queue, Semaphore
from dataclasses import dataclass
from typing import Callable

from ..constants.defaults import (
    DEFAULT_BENCHMARK_ENABLED,
    DEFAULT_BENCHMARK_EXPECTED_COUNT,
    DEFAULT_BENCHMARK_WORKERS,
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_RESOLVE_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
)
from ..enums import JobStatus
from ..integrations import MangaDexApiClient
from ..utils import DownloadClient, MultiFormatExporter
from .base import WorkerConfig
from .benchmark_worker import BenchmarkWorker
from .download_worker import DownloadWorker
from .jobs import (
    FetchingResourcesJob,
    Job,
)
from .merge_worker import MergeWorker
from .resolve_worker import ResolveWorker

logger = logging.getLogger(__name__)


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

    num_resolve_workers: int = DEFAULT_RESOLVE_WORKERS
    num_download_workers: int = DEFAULT_DOWNLOAD_WORKERS
    num_merge_workers: int = DEFAULT_MERGE_WORKERS

    resolve_rate_limit: int = DEFAULT_RESOLVE_RATE_LIMIT
    download_rate_limit: int = DEFAULT_DOWNLOAD_RATE_LIMIT

    benchmark_enabled: bool = DEFAULT_BENCHMARK_ENABLED
    benchmark_expected_count: int | None = DEFAULT_BENCHMARK_EXPECTED_COUNT


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
        self._resolve_queue: Queue[Job] = Queue()
        self._download_queue: Queue[Job] = Queue()
        self._merge_queue: Queue[Job] = Queue()
        self._benchmark_queue: Queue[Job] = Queue()

        self._resolve_semaphore: Semaphore = Semaphore(config.resolve_rate_limit)
        self._download_semaphore: Semaphore = Semaphore(config.download_rate_limit)

        self._resolve_pool: list[ResolveWorker] = [
            ResolveWorker(
                id=f"resolve_worker_{index}",
                input_queue=self._resolve_queue,
                output_queue=self._download_queue,
                on_status_change=on_status_change,
                config=WorkerConfig(),
                api_client=mangadex_api_client,
                semaphore=self._resolve_semaphore,
            )
            for index in range(config.num_resolve_workers)
        ]
        self._download_pool: list[DownloadWorker] = [
            DownloadWorker(
                id=f"download_worker_{index}",
                input_queue=self._download_queue,
                output_queue=self._merge_queue,
                on_status_change=on_status_change,
                config=WorkerConfig(),
                download_client=download_client,
                semaphore=self._download_semaphore,
            )
            for index in range(config.num_download_workers)
        ]
        self._merge_pool: list[MergeWorker] = [
            MergeWorker(
                id=f"merge_worker_{index}",
                input_queue=self._merge_queue,
                output_queue=(
                    self._benchmark_queue if config.benchmark_enabled else None
                ),
                on_status_change=on_status_change,
                config=WorkerConfig(),
                multi_format_exporter=MultiFormatExporter(),
            )
            for index in range(config.num_merge_workers)
        ]

        self._benchmark_pool: list[BenchmarkWorker] = []
        self._track_memory = config.benchmark_enabled
        self._benchmark_callback = benchmark_callback

        if config.benchmark_enabled:
            wrapped_callback = self._wrap_benchmark_callback(benchmark_callback)
            self._benchmark_pool = [
                BenchmarkWorker(
                    id=f"benchmark_worker_{index}",
                    input_queue=self._benchmark_queue,
                    output_queue=None,
                    on_status_change=on_status_change,
                    config=WorkerConfig(),
                    expected_count=config.benchmark_expected_count,
                    benchmark_callback=wrapped_callback,
                )
                for index in range(DEFAULT_BENCHMARK_WORKERS)
            ]

    async def enqueue_jobs(self, jobs: list[FetchingResourcesJob]):
        for job in jobs:
            await self._resolve_queue.put(job)

    def _wrap_benchmark_callback(
        self, original_callback: Callable[[float, float], None] | None
    ) -> Callable[[float, float], None]:
        """Wrap benchmark callback to include memory logging."""

        def wrapped_callback(earliest_start: float, latest_end: float) -> None:
            if self._track_memory:
                _, peak = tracemalloc.get_traced_memory()
                peak_mb = peak / 1024 / 1024
                logger.debug(
                    "Benchmark: time=%.2fms, peak_memory=%.2fMB",
                    (latest_end - earliest_start) / 1_000_000,
                    peak_mb,
                )

            if original_callback:
                original_callback(earliest_start, latest_end)

        return wrapped_callback

    async def start(self):
        if self._track_memory:
            tracemalloc.start()

        all_workers = (
            self._resolve_pool
            + self._download_pool
            + self._merge_pool
            + self._benchmark_pool
        )

        await asyncio.gather(*[w.run() for w in all_workers])

    async def stop(self):
        for worker in self._resolve_pool:
            worker.stop()
