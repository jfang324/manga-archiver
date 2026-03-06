"""Unit tests for SessionManager."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from src.mangadex_downloader.utils.session_manager import SessionManager


class TestSessionManagerCreateSession:
    """Test create_session method."""

    @patch("aiohttp.ClientSession")
    def test_create_session_creates_new_session(self, mock_session_class):
        """Test that create_session creates a new session when none exists."""
        # Reset singleton state
        SessionManager._session = None
        
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        result = SessionManager.create_session()
        
        assert result == mock_session
        assert SessionManager._session == mock_session

    @patch("aiohttp.ClientSession")
    def test_create_session_reuses_existing_session(self, mock_session_class):
        """Test that create_session returns existing session if one exists."""
        # Reset and create initial session
        SessionManager._session = None
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        # First call creates session
        SessionManager.create_session()
        
        # Second call should return existing session
        result = SessionManager.create_session()
        
        # ClientSession should only be called once
        assert mock_session_class.call_count == 1
        assert result == mock_session

    @patch("aiohttp.ClientSession")
    def test_create_session_returns_aiohttp_session(self, mock_session_class):
        """Test that create_session returns an aiohttp ClientSession."""
        SessionManager._session = None
        mock_session = MagicMock()
        mock_session_class.return_value = mock_session
        
        result = SessionManager.create_session()
        
        assert result is not None
        mock_session_class.assert_called_once()


class TestSessionManagerCloseSession:
    """Test close_session method."""

    @pytest.mark.asyncio
    async def test_close_session_closes_existing_session(self):
        """Test that close_session closes and clears existing session."""
        # Setup
        mock_session = MagicMock()
        mock_session.close = AsyncMock()
        SessionManager._session = mock_session
        
        # Execute
        await SessionManager.close_session()
        
        # Verify
        mock_session.close.assert_called_once()
        assert SessionManager._session is None

    @pytest.mark.asyncio
    async def test_close_session_no_session_exists(self):
        """Test that close_session handles case when no session exists."""
        # Setup
        SessionManager._session = None
        
        # Execute - should not raise
        await SessionManager.close_session()
        
        # Verify
        assert SessionManager._session is None

    @pytest.mark.asyncio
    async def test_close_session_after_recreate(self):
        """Test closing session after creating a new one."""
        # Setup
        mock_session1 = MagicMock()
        mock_session1.close = AsyncMock()
        mock_session2 = MagicMock()
        mock_session2.close = AsyncMock()
        
        with patch("aiohttp.ClientSession") as mock_session_class:
            mock_session_class.side_effect = [mock_session1, mock_session2]
            
            # Create first session
            SessionManager._session = None
            SessionManager.create_session()
            
            # Close it
            await SessionManager.close_session()
            
            # Create second session
            SessionManager.create_session()
            
            # Close second session
            await SessionManager.close_session()
        
        # Both sessions should be closed
        mock_session1.close.assert_called_once()
        mock_session2.close.assert_called_once()
