import asyncio
import json
from pathlib import Path
from typing import TypedDict

from .utils import get_root_path
from .validation import require_mapping, required_str

TOKEN_FILENAME = "google_drive_token.json"  # noqa: S105 - local filename, not a credential


class GoogleApiStoredToken(TypedDict):
    """Persisted metadata for google.oauth2.credentials.Credentials."""

    token_uri: str
    client_id: str
    client_secret: str
    refresh_token: str


class GoogleDriveTokenStore:
    """Persists Google Drive OAuth token data between sessions."""

    def __init__(self, token_path: Path | None = None) -> None:
        self._token_path = token_path or get_root_path() / TOKEN_FILENAME

    async def load(self) -> GoogleApiStoredToken | None:
        """Load stored token from disk."""
        if not await asyncio.to_thread(self._token_path.exists):
            return None

        try:
            parsed_token = json.loads(await asyncio.to_thread(self._token_path.read_text))
        except (json.JSONDecodeError, OSError):
            return None

        try:
            return _parse_token(parsed_token)
        except ValueError:
            return None

    async def save(self, token: GoogleApiStoredToken) -> None:
        """Store token to disk."""
        await asyncio.to_thread(self._token_path.parent.mkdir, parents=True, exist_ok=True)
        await asyncio.to_thread(self._token_path.write_text, json.dumps(token, indent=2))

    async def delete(self) -> None:
        """Delete stored token."""
        await asyncio.to_thread(self._token_path.unlink, missing_ok=True)


def _parse_token(raw_token: object) -> GoogleApiStoredToken:
    token = require_mapping(raw_token, "Google Drive token")
    return GoogleApiStoredToken(
        token_uri=required_str(token, "token_uri"),
        client_id=required_str(token, "client_id"),
        client_secret=required_str(token, "client_secret"),
        refresh_token=required_str(token, "refresh_token"),
    )
