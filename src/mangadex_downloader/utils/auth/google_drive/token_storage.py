import json
import logging
import os
from pathlib import Path

from .types import GoogleApiStoredToken

logger = logging.getLogger(__name__)

TOKEN_FILENAME = "google_drive_token.json"  # noqa: S105


def get_token_path() -> Path:
    """Get the path to the token file."""

    config_dir = Path(os.path.expanduser("~/.mangadex-downloader"))
    return config_dir / TOKEN_FILENAME


def load_token() -> GoogleApiStoredToken | None:
    """Load stored token from disk."""
    token_file = get_token_path()
    if not token_file.exists():
        return None

    try:
        return json.loads(token_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load token: %s", e)
        return None


def save_token(token: GoogleApiStoredToken) -> None:
    """Store token to disk."""
    token_file = get_token_path()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(json.dumps(token, indent=2))
    logger.debug("Token saved to %s", token_file)


def delete_token() -> None:
    """Delete stored token."""
    token_file = get_token_path()

    if token_file.exists():
        token_file.unlink()
        logger.debug("Token deleted")
