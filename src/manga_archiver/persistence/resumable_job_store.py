import asyncio
import json
from pathlib import Path
from typing import TypedDict

from ..models import ContentSource
from ..models.app_config import AppConfig
from ..models.output_format import OutputFormat
from ..workers.jobs import FetchingResourcesJob
from .utils import get_root_path
from .validation import (
    require_mapping,
    required_bool,
    required_float,
    required_int,
    required_str,
)

RESUMABLE_JOBS_FILENAME = "resumable-jobs.json"


class SerializedAppConfig(TypedDict):
    """Serialized AppConfig fields persisted in the resume store."""

    output_path: str
    output_format: str
    quality: int
    optimize: bool
    data_saver: bool


class SerializedFetchingResourcesJob(TypedDict):
    """Serialized FetchingResourcesJob fields persisted in the resume store."""

    id: str
    manga_title: str
    chapter_id: str
    chapter_number: float
    chapter_title: str
    app_config: SerializedAppConfig
    source: str
    payload_size: int


class ResumableJobStore:
    """Persists resumable fetch jobs between application sessions."""

    def __init__(self, resume_store_path: Path | None = None) -> None:
        self._resume_store_path = resume_store_path or get_root_path() / RESUMABLE_JOBS_FILENAME

    async def save_resumable_jobs(self, jobs: list[FetchingResourcesJob]) -> None:
        """Save resumable jobs to the resume store."""
        for job in jobs:
            if not isinstance(job, FetchingResourcesJob):
                raise ValueError("Resume store can only save FetchingResourcesJob instances")

        serialized_jobs = [_serialize_fetching_resources_job(job) for job in jobs]

        try:
            await asyncio.to_thread(
                self._resume_store_path.parent.mkdir, parents=True, exist_ok=True
            )
            await asyncio.to_thread(
                self._resume_store_path.write_text,
                json.dumps(serialized_jobs, indent=2),
            )
        except OSError as e:
            raise ValueError(f"Failed to save {RESUMABLE_JOBS_FILENAME}: {e}") from e

    async def clear_resumable_jobs(self) -> None:
        """Clear resumable jobs from the resume store."""
        try:
            await asyncio.to_thread(self._resume_store_path.unlink, missing_ok=True)
        except OSError as e:
            raise ValueError(f"Failed to clear {RESUMABLE_JOBS_FILENAME}: {e}") from e

    async def get_resumable_jobs(self) -> list[FetchingResourcesJob]:
        """Get a list of resumable jobs from the resume store.

        Returns:
            list[FetchingResourcesJob]: Jobs that can be requeued.
        """
        if not await asyncio.to_thread(self._resume_store_path.exists):
            return []

        try:
            raw_data = json.loads(await asyncio.to_thread(self._resume_store_path.read_text))
        except (json.JSONDecodeError, OSError):
            await self.clear_resumable_jobs()
            return []

        if not isinstance(raw_data, list):
            await self.clear_resumable_jobs()
            return []

        resumable_jobs: list[FetchingResourcesJob] = []

        for raw_job in raw_data:
            try:
                job_data = _parse_fetching_resources_job(raw_job)
                resumable_jobs.append(_create_fetching_resources_job(job_data))
            except ValueError:  # noqa: PERF203
                continue

        return resumable_jobs


def _serialize_fetching_resources_job(
    job: FetchingResourcesJob,
) -> SerializedFetchingResourcesJob:
    return SerializedFetchingResourcesJob(
        id=job.id,
        manga_title=job.manga_title,
        chapter_id=job.chapter_id,
        chapter_number=job.chapter_number,
        chapter_title=job.chapter_title,
        app_config=_serialize_app_config(job.app_config),
        source=str(job.source),
        payload_size=job.payload_size,
    )


def _serialize_app_config(app_config: AppConfig) -> SerializedAppConfig:
    return SerializedAppConfig(
        output_path=str(app_config.output_path),
        output_format=str(app_config.output_format),
        quality=app_config.quality,
        optimize=app_config.optimize,
        data_saver=app_config.data_saver,
    )


def _parse_fetching_resources_job(raw_data: object) -> SerializedFetchingResourcesJob:
    raw_job = require_mapping(raw_data, "resumable job")

    return SerializedFetchingResourcesJob(
        id=required_str(raw_job, "id"),
        manga_title=required_str(raw_job, "manga_title"),
        chapter_id=required_str(raw_job, "chapter_id"),
        chapter_number=required_float(raw_job, "chapter_number"),
        chapter_title=required_str(raw_job, "chapter_title"),
        app_config=_parse_app_config(raw_job.get("app_config")),
        source=required_str(raw_job, "source"),
        payload_size=required_int(raw_job, "payload_size"),
    )


def _parse_app_config(raw_data: object) -> SerializedAppConfig:
    raw_config = require_mapping(raw_data, "app_config")

    return SerializedAppConfig(
        output_path=required_str(raw_config, "output_path"),
        output_format=required_str(raw_config, "output_format"),
        quality=required_int(raw_config, "quality"),
        optimize=required_bool(raw_config, "optimize"),
        data_saver=required_bool(raw_config, "data_saver"),
    )


def _create_fetching_resources_job(
    job_data: SerializedFetchingResourcesJob,
) -> FetchingResourcesJob:
    app_config = job_data["app_config"]

    return FetchingResourcesJob(
        id=job_data["id"],
        manga_title=job_data["manga_title"],
        chapter_number=job_data["chapter_number"],
        chapter_title=job_data["chapter_title"],
        app_config=AppConfig(
            _output_path=Path(app_config["output_path"]),
            _output_format=OutputFormat(app_config["output_format"]),
            _quality=app_config["quality"],
            optimize=app_config["optimize"],
            data_saver=app_config["data_saver"],
        ),
        source=ContentSource(job_data["source"]),
        payload_size=job_data["payload_size"],
        chapter_id=job_data["chapter_id"],
    )
