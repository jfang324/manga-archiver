import json
import logging
import os
from pathlib import Path

logger = logging.getLogger(__name__)

TOKEN_FILENAME = "google_drive_token.json"


def get_token_path() -> Path:
    config_dir = Path(os.path.expanduser("~/.mangadex-downloader"))
    return config_dir / TOKEN_FILENAME


def load_token() -> dict | None:
    """Load stored token from disk.

    Returns:
        Token dict if exists and valid, None otherwise.
    """
    token_file = get_token_path()
    if not token_file.exists():
        return None

    try:
        return json.loads(token_file.read_text())
    except (json.JSONDecodeError, OSError) as e:
        logger.error("Failed to load token: %s", e)
        return None


def save_token(token: dict) -> None:
    """Store token to disk.

    Args:
        token: Token dict to store.
    """
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
