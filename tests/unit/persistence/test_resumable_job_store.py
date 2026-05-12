import json
from pathlib import Path
from typing import cast

import pytest

from src.manga_archiver.models import ContentSource
from src.manga_archiver.models.app_config import AppConfig
from src.manga_archiver.models.output_format import OutputFormat
from src.manga_archiver.persistence.resumable_job_store import ResumableJobStore
from src.manga_archiver.workers.jobs import FetchingResourcesJob


def _valid_job_data(output_path: str) -> dict:
    return {
        "id": "chapter_123",
        "manga_title": "Test Manga",
        "chapter_id": "chapter_123",
        "chapter_number": 1.0,
        "chapter_title": "Chapter 1",
        "app_config": {
            "output_path": output_path,
            "output_format": "pdf",
            "quality": 85,
            "optimize": True,
            "data_saver": False,
        },
        "source": "mangadex",
        "payload_size": 0,
    }


def _fetching_resources_job(output_path: Path) -> FetchingResourcesJob:
    return FetchingResourcesJob(
        id="chapter_123",
        manga_title="Test Manga",
        chapter_id="chapter_123",
        chapter_number=1.0,
        chapter_title="Chapter 1",
        app_config=AppConfig(
            _output_path=output_path,
            _output_format=OutputFormat.PDF,
            _quality=85,
            optimize=True,
            data_saver=False,
        ),
        source=ContentSource.MANGADEX,
        payload_size=0,
    )


class TestResumableJobStore:
    def test_save_resumable_jobs_writes_serialized_jobs(self, tmp_path) -> None:
        resume_store_path = tmp_path / "nested" / "resumable-jobs.json"
        store = ResumableJobStore(resume_store_path)
        job = _fetching_resources_job(tmp_path)

        store.save_resumable_jobs([job])

        assert json.loads(resume_store_path.read_text()) == [_valid_job_data(str(tmp_path))]

    def test_save_resumable_jobs_round_trips_resumable_jobs(self, tmp_path) -> None:
        resume_store_path = tmp_path / "resumable-jobs.json"
        store = ResumableJobStore(resume_store_path)
        job = _fetching_resources_job(tmp_path)

        store.save_resumable_jobs([job])
        loaded_jobs = store.get_resumable_jobs()

        assert loaded_jobs == [job]

    def test_save_resumable_jobs_raises_for_invalid_job_type(self, tmp_path) -> None:
        store = ResumableJobStore(tmp_path / "resumable-jobs.json")

        with pytest.raises(ValueError, match="FetchingResourcesJob"):
            store.save_resumable_jobs(cast(list[FetchingResourcesJob], ["not-a-job"]))

    def test_clear_resumable_jobs_removes_resume_store_file(self, tmp_path) -> None:
        resume_store_path = tmp_path / "resumable-jobs.json"
        resume_store_path.write_text(json.dumps([_valid_job_data(str(tmp_path))]))
        store = ResumableJobStore(resume_store_path)

        store.clear_resumable_jobs()

        assert not resume_store_path.exists()

    def test_get_resumable_jobs_returns_fetching_resources_jobs(self, tmp_path) -> None:
        resume_store_path = tmp_path / "resumable-jobs.json"
        resume_store_path.write_text(json.dumps([_valid_job_data(str(tmp_path))]))
        store = ResumableJobStore(resume_store_path)

        jobs = store.get_resumable_jobs()

        assert len(jobs) == 1
        job = jobs[0]
        assert isinstance(job, FetchingResourcesJob)
        assert job.id == "chapter_123"
        assert job.manga_title == "Test Manga"
        assert job.chapter_id == "chapter_123"
        assert job.chapter_number == 1.0
        assert job.chapter_title == "Chapter 1"
        assert job.app_config.output_path == tmp_path
        assert job.app_config.output_format == OutputFormat.PDF
        assert job.app_config.quality == 85
        assert job.app_config.optimize is True
        assert job.app_config.data_saver is False
        assert job.source == ContentSource.MANGADEX
        assert job.payload_size == 0

    @pytest.mark.parametrize(
        "resume_store_contents",
        [
            "{ invalid json",
            json.dumps({"jobs": []}),
        ],
        ids=["malformed_json", "non_list_json"],
    )
    def test_get_resumable_jobs_returns_empty_list_for_invalid_file_shape(
        self, tmp_path, resume_store_contents: str
    ) -> None:
        resume_store_path = tmp_path / "resumable-jobs.json"
        resume_store_path.write_text(resume_store_contents)
        store = ResumableJobStore(resume_store_path)

        assert store.get_resumable_jobs() == []
        assert not resume_store_path.exists()

    def test_get_resumable_jobs_skips_invalid_records(self, tmp_path) -> None:
        valid_job = _valid_job_data(str(tmp_path))
        invalid_job = _valid_job_data(str(tmp_path))
        invalid_job.pop("chapter_id")
        resume_store_path = tmp_path / "resumable-jobs.json"
        resume_store_path.write_text(json.dumps([invalid_job, valid_job]))
        store = ResumableJobStore(resume_store_path)

        jobs = store.get_resumable_jobs()

        assert len(jobs) == 1
        assert jobs[0].id == "chapter_123"

    @pytest.mark.parametrize(
        "field_name, invalid_value",
        [
            ("source", "unknown"),
            ("output_format", "unknown"),
        ],
        ids=["invalid_source", "invalid_output_format"],
    )
    def test_get_resumable_jobs_skips_invalid_enum_values(
        self, tmp_path, field_name: str, invalid_value: str
    ) -> None:
        invalid_job = _valid_job_data(str(tmp_path))
        if field_name == "output_format":
            invalid_job["app_config"]["output_format"] = invalid_value
        else:
            invalid_job[field_name] = invalid_value
        resume_store_path = tmp_path / "resumable-jobs.json"
        resume_store_path.write_text(json.dumps([invalid_job]))
        store = ResumableJobStore(resume_store_path)

        assert store.get_resumable_jobs() == []
