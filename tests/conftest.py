from unittest.mock import AsyncMock, MagicMock

import pytest


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

    return response
