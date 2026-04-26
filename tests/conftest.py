import asyncio
from collections.abc import Callable
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.manga_archiver.workers.jobs import Job


class AsyncContextManagerMock:
    """Helper class to create async context manager mocks."""

    def __init__(self, response) -> None:
        self.response = response

    async def __aenter__(self) -> MagicMock:
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        return None


class TaskTracker:
    """Track created asyncio tasks and provide side_effect for patching."""

    def __init__(self) -> None:
        self._original_create_task = asyncio.create_task
        self.tasks: list[asyncio.Task] = []

    def __call__(self, coro) -> asyncio.Task:
        task = self._original_create_task(coro)
        task.cancel = MagicMock(wraps=task.cancel)
        self.tasks.append(task)
        return task


@pytest.fixture
def mock_session() -> MagicMock:
    """
    Create a mock aiohttp ClientSession.

    Usage in tests:
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
    """
    return MagicMock()


@pytest.fixture
def mock_api_response(request) -> MagicMock:
    status_code, return_value = request.param
    response = MagicMock()
    response.status = status_code

    response.json = AsyncMock(return_value=return_value)
    response.read = AsyncMock(return_value=return_value)

    return response


@pytest.fixture
def task_tracker() -> TaskTracker:
    """Track created asyncio tasks and provide side_effect for patching."""
    return TaskTracker()


@pytest.fixture
def mock_api_response_list(request) -> Callable:
    """Fixture for tests that need multiple responses (e.g., download_images)."""
    responses_list = request.param
    mock_responses = [
        MagicMock(
            status=status_code,
            read=AsyncMock(return_value=data) if data else None,
        )
        for status_code, data in responses_list
    ]

    response_iter = iter(mock_responses)
    return lambda *args, **kwargs: AsyncContextManagerMock(next(response_iter))  # noqa: ARG005


@pytest.fixture
def mock_job() -> MagicMock:
    """Create a mock Job for testing workers."""
    job = MagicMock(spec=Job)
    job.id = "test_job"
    job.manga_title = "Test Manga"
    job.chapter_number = 1.0
    job.chapter_title = "Chapter 1"
    job.output_directory = MagicMock()
    job.output_format = MagicMock()
    return job


@pytest.fixture
def mock_semaphore() -> MagicMock:
    """Create a mock asyncio Semaphore for testing workers."""
    semaphore = MagicMock()
    semaphore.__aenter__ = AsyncMock()
    semaphore.__aexit__ = AsyncMock()
    return semaphore
