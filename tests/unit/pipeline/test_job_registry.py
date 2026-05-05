import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.pipeline.job_registry import PipelineJobRegistry
from src.manga_archiver.workers.types import JobMetadata, JobStatus


@pytest.fixture
def job_metadata(tmp_path) -> JobMetadata:
    return JobMetadata(
        manga_title="Test Manga",
        chapter_number=1.0,
        chapter_title="Chapter 1",
        chapter_id="chapter_123",
        app_config=AppConfig(_output_path=tmp_path),
        source=ContentSource.MANGADEX,
    )


class TestPipelineJobRegistry:
    def test_record_status_update_records_latest_status(self, job_metadata: JobMetadata) -> None:
        registry = PipelineJobRegistry()

        registry.record_status_update("job_123", JobStatus.QUEUED, job_metadata)
        registry.record_status_update("job_123", JobStatus.DOWNLOADING, job_metadata)

        assert registry.get_jobs() == {"job_123": (JobStatus.DOWNLOADING, job_metadata)}

    def test_incomplete_job_count_excludes_terminal_jobs(self, job_metadata: JobMetadata) -> None:
        registry = PipelineJobRegistry()

        registry.record_status_update("queued", JobStatus.QUEUED, job_metadata)
        registry.record_status_update("completed", JobStatus.COMPLETED, job_metadata)
        registry.record_status_update("failed", JobStatus.FAILED, job_metadata)

        assert registry.incomplete_job_count() == 1

    def test_pop_failed_jobs_returns_and_clears_failed_jobs(
        self, job_metadata: JobMetadata
    ) -> None:
        registry = PipelineJobRegistry()

        registry.record_status_update("job_123", JobStatus.FAILED, job_metadata)

        failed_jobs = registry.pop_failed_jobs()

        assert len(failed_jobs) == 1
        assert failed_jobs[0].id == "job_123"
        assert failed_jobs[0].chapter_id == job_metadata.chapter_id
        assert registry.pop_failed_jobs() == []

    def test_completed_status_removes_failed_job(self, job_metadata: JobMetadata) -> None:
        registry = PipelineJobRegistry()

        registry.record_status_update("job_123", JobStatus.FAILED, job_metadata)
        registry.record_status_update("job_123", JobStatus.COMPLETED, job_metadata)

        assert registry.pop_failed_jobs() == []

    def test_terminal_jobs_expire_after_expiry_window(self, job_metadata: JobMetadata) -> None:
        now = 100.0
        registry = PipelineJobRegistry(
            job_expiry_seconds=10,
            time_provider=lambda: now,
        )

        registry.record_status_update("job_123", JobStatus.COMPLETED, job_metadata)
        now = 111.0
        registry.record_status_update("job_456", JobStatus.QUEUED, job_metadata)

        assert registry.get_jobs() == {"job_456": (JobStatus.QUEUED, job_metadata)}

    def test_get_jobs_returns_copy(self, job_metadata: JobMetadata) -> None:
        registry = PipelineJobRegistry()
        registry.record_status_update("job_123", JobStatus.QUEUED, job_metadata)

        jobs = registry.get_jobs()
        jobs.clear()

        assert registry.get_jobs() == {"job_123": (JobStatus.QUEUED, job_metadata)}
