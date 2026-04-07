from unittest.mock import AsyncMock, MagicMock

import pytest

from src.mangadex_downloader.workers.jobs import Job


class AsyncContextManagerMock:
    """Helper class to create async context manager mocks."""

    def __init__(self, response):
        self.response = response

    async def __aenter__(self):
        return self.response

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        return None


@pytest.fixture
def mock_session():
    """
    Create a mock aiohttp ClientSession.

    Usage in tests:
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
    """
    session = MagicMock()
    # Don't set return_value here - let tests set it explicitly
    return session


@pytest.fixture
def mock_api_response(request):
    status_code, return_value = request.param
    response = MagicMock()
    response.status = status_code

    response.json = AsyncMock(return_value=return_value)
    response.read = AsyncMock(return_value=return_value)

    return response


@pytest.fixture
def task_tracker():
    """Track created asyncio tasks and provide side_effect for patching."""
    import asyncio

    original_create_task = asyncio.create_task

    class TaskTracker:
        def __init__(self):
            self.tasks = []

        def __call__(self, coro):
            task = original_create_task(coro)
            task.cancel = MagicMock(wraps=task.cancel)
            self.tasks.append(task)
            return task

    return TaskTracker()


@pytest.fixture
def mock_api_response_list(request):
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
    return lambda *args, **kwargs: AsyncContextManagerMock(next(response_iter))


@pytest.fixture
def mock_job():
    """Create a mock Job for testing workers."""
    job = MagicMock(spec=Job)
    job.id = "test_job"
    job.manga_title = "Test Manga"
    job.chapter_title = "Chapter 1"
    job.output_directory = MagicMock()
    job.output_format = MagicMock()
    return job


@pytest.fixture
def mock_semaphore():
    """Create a mock asyncio Semaphore for testing workers."""
    semaphore = MagicMock()
    semaphore.__aenter__ = AsyncMock()
    semaphore.__aexit__ = AsyncMock()
    return semaphore
