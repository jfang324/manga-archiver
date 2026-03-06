"""Session management utilities."""

from typing import Optional

import aiohttp


class SessionManager:
    """Singleton manager for aiohttp ClientSession.

    Ensures only one session exists and provides centralized cleanup.
    """

    _session: Optional[aiohttp.ClientSession] = None

    @staticmethod
    def create_session() -> aiohttp.ClientSession:
        """Create a new session if one doesn't exist.

        :return: The aiohttp ClientSession instance
        """
        if SessionManager._session is None:
            SessionManager._session = aiohttp.ClientSession()

        return SessionManager._session

    @staticmethod
    async def close_session() -> None:
        """Close the session and clean up resources."""
        if SessionManager._session is not None:
            await SessionManager._session.close()
            SessionManager._session = None
