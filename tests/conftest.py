"""Pytest fixtures and configuration."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch


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
    """Create a mock aiohttp ClientSession.
    
    Usage in tests:
        mock_session.get.return_value = AsyncContextManagerMock(mock_response)
    """
    session = MagicMock()
    # Don't set return_value here - let tests set it explicitly
    return session


@pytest.fixture
def mock_response():
    """Create a mock aiohttp response object."""
    response = MagicMock()
    response.status = 200
    response.json = AsyncMock(return_value={})
    response.read = AsyncMock(return_value=b"mock_image_data")
    return response


@pytest.fixture
def mock_curses_window():
    """Create a mock curses window object."""
    window = MagicMock()
    window.clear = MagicMock()
    window.addstr = MagicMock()
    window.refresh = MagicMock()
    window.getch = MagicMock(return_value=10)  # Enter key
    return window


@pytest.fixture(autouse=True)
def reset_session_manager():
    """Reset SessionManager singleton before each test."""
    from src.mangadex_downloader.utils.session_manager import SessionManager
    SessionManager._session = None
    yield
    SessionManager._session = None
