from typing import cast
from unittest.mock import MagicMock

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.pipeline import PipelineConfig, PipelineManager
from src.manga_archiver.pipeline.benchmark import BenchmarkAggregates
from src.manga_archiver.workers.jobs import FetchingResourcesJob
from src.manga_archiver.workers.types import JobStatus


def _benchmark_aggregates() -> BenchmarkAggregates:
    return BenchmarkAggregates(
        total_time_per_phase={
            JobStatus.FETCHING_RESOURCES: 1_000_000,
            JobStatus.DOWNLOADING: 2_000_000,
            JobStatus.MERGING: 3_000_000,
            JobStatus.UPLOADING: 4_000_000,
        },
        avg_time_per_phase={
            JobStatus.FETCHING_RESOURCES: 1_000_000,
            JobStatus.DOWNLOADING: 2_000_000,
            JobStatus.MERGING: 3_000_000,
            JobStatus.UPLOADING: 4_000_000,
        },
        avg_total_time=10_000_000,
        peak_memory_mb=12.5,
        total_job_count=3,
        highest_perceived_download_time=5_000_000,
        highest_perceived_end_to_end=6_000_000,
    )


class TestPipelineValidation:
    @pytest.mark.parametrize(
        "invalid_fields, expected_error_message",
        [
            ({"id": ""}, "Job is missing id"),
            ({"manga_title": ""}, "is missing manga_title"),
            ({"chapter_number": None}, "must be float type"),
            ({"chapter_number": "not-a-number"}, "must be float type"),
            ({"chapter_title": ""}, "is missing chapter_title"),
            ({"chapter_id": ""}, "is missing chapter_id"),
            ({"app_config": None}, "app_config must be AppConfig instance"),
        ],
        ids=[
            "missing_id",
            "missing_manga_title",
            "missing_chapter_number",
            "invalid_chapter_number",
            "missing_chapter_title",
            "missing_chapter_id",
            "missing_app_config",
        ],
    )
    def test_validate_job_raises_on_invalid_field(
        self, tmp_path, invalid_fields, expected_error_message
    ) -> None:
        job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_456",
            app_config=AppConfig(_output_path=tmp_path, _output_format=OutputFormat.PDF),
            source=ContentSource.MANGADEX,
        )

        for key, value in invalid_fields.items():
            setattr(job, key, value)

        pm = PipelineManager(
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            config=PipelineConfig(),
            google_drive_token=None,
        )

        with pytest.raises(ValueError, match=expected_error_message):
            pm._validate_job(job)


class TestPipelineEnqueue:
    async def test_enqueue_jobs_reports_accepted_and_skipped_jobs(self, tmp_path) -> None:
        valid_job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_123",
            app_config=AppConfig(_output_path=tmp_path, _output_format=OutputFormat.PDF),
            source=ContentSource.MANGADEX,
        )
        invalid_job = FetchingResourcesJob(
            id="job_456",
            manga_title="Test Manga",
            chapter_number=2.0,
            chapter_title="Chapter 2",
            chapter_id="chapter_456",
            app_config=cast(AppConfig, None),
            source=ContentSource.MANGADEX,
        )
        pm = PipelineManager(
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            config=PipelineConfig(resolve_scheduler_enabled=False),
            google_drive_token=None,
        )

        result = await pm.enqueue_jobs([valid_job, invalid_job])

        assert result.accepted_count == 1
        assert result.skipped_count == 1

    async def test_enqueue_jobs_skips_duplicate_chapter_ids(self, tmp_path) -> None:
        first_job = FetchingResourcesJob(
            id="job_123",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1",
            chapter_id="chapter_123",
            app_config=AppConfig(_output_path=tmp_path, _output_format=OutputFormat.PDF),
            source=ContentSource.MANGADEX,
        )
        duplicate_job = FetchingResourcesJob(
            id="job_456",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1 Duplicate",
            chapter_id="chapter_123",
            app_config=AppConfig(_output_path=tmp_path, _output_format=OutputFormat.PDF),
            source=ContentSource.MANGADEX,
        )
        pm = PipelineManager(
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            config=PipelineConfig(resolve_scheduler_enabled=False),
            google_drive_token=None,
        )

        result = await pm.enqueue_jobs([first_job, duplicate_job])

        assert result.accepted_count == 1
        assert result.skipped_count == 1


class TestPipelineBenchmark:
    def test_get_benchmark_results_returns_none_when_disabled(self) -> None:
        pm = PipelineManager(
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            config=PipelineConfig(benchmark_enabled=False),
            google_drive_token=None,
        )

        assert pm.get_benchmark_results() is None

    def test_get_benchmark_results_uses_worker_manager_aggregates(self) -> None:
        pm = PipelineManager(
            provider_manager=MagicMock(),
            download_client=MagicMock(),
            config=PipelineConfig(benchmark_enabled=True),
            google_drive_token=None,
        )
        pm._worker_manager.get_benchmark_aggregates = MagicMock(
            return_value=_benchmark_aggregates()
        )

        result = pm.get_benchmark_results()

        assert result == {
            "total_job_count": 3,
            "fetching_total_ms": 1.0,
            "fetching_avg_ms": 1.0,
            "downloading_total_ms": 2.0,
            "downloading_avg_ms": 2.0,
            "merging_total_ms": 3.0,
            "merging_avg_ms": 3.0,
            "uploading_total_ms": 4.0,
            "uploading_avg_ms": 4.0,
            "avg_total_time_ms": 10.0,
            "peak_memory_mb": 12.5,
            "highest_perceived_download_time_ms": 5.0,
            "highest_perceived_end_to_end_ms": 6.0,
        }
        pm._worker_manager.get_benchmark_aggregates.assert_called_once_with()
