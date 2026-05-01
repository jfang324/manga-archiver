from pathlib import Path
from unittest.mock import MagicMock

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.pipeline_manager import PipelineConfig, PipelineManager
from src.manga_archiver.workers.jobs import FetchingResourcesJob


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
            ({"output_format": None}, "output_format must be OutputFormat"),
            ({"output_directory": None}, "output_directory"),
            ({"output_directory": Path("/nonexistent/path")}, "output_directory does not exist"),
        ],
        ids=[
            "missing_id",
            "missing_manga_title",
            "missing_chapter_number",
            "invalid_chapter_number",
            "missing_chapter_title",
            "missing_chapter_id",
            "none_output_format",
            "none_output_directory",
            "nonexistent_output_directory",
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
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
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
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            source=ContentSource.MANGADEX,
        )
        invalid_job = FetchingResourcesJob(
            id="job_456",
            manga_title="Test Manga",
            chapter_number=2.0,
            chapter_title="Chapter 2",
            chapter_id="chapter_456",
            output_directory=tmp_path / "missing",
            output_format=OutputFormat.PDF,
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
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
            source=ContentSource.MANGADEX,
        )
        duplicate_job = FetchingResourcesJob(
            id="job_456",
            manga_title="Test Manga",
            chapter_number=1.0,
            chapter_title="Chapter 1 Duplicate",
            chapter_id="chapter_123",
            output_directory=tmp_path,
            output_format=OutputFormat.PDF,
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
