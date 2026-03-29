from aiohttp import ClientSession


class SessionManager:
    """
    Singleton manager for aiohttp ClientSession.
    """

    _session: ClientSession | None = None

    @staticmethod
    def create_session() -> ClientSession:
        """
        Create a new session if one doesn't exist.

        Returns:
            ClientSession: The aiohttp ClientSession instance
        """
        if SessionManager._session is None:
            SessionManager._session = ClientSession()

        return SessionManager._session

    @staticmethod
    async def close_session() -> None:
        if SessionManager._session is not None:
            await SessionManager._session.close()

            SessionManager._session = None
