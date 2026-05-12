import os
from pathlib import Path


def get_root_path() -> Path:
    """Get the root directory for the application."""

    return Path(os.path.expanduser("~/.manga-archiver"))
