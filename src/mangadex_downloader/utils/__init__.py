"""Utility functions for the MangaDex downloader."""

import re

from .downloader import DownloadClient
from .multi_format_exporter import MultiFormatExporter
from .session_manager import SessionManager


def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be used as a filename.

    Removes or replaces characters that are invalid or problematic in filenames.

    Args:
        filename: The filename to sanitize

    Returns:
        The sanitized filename
    """
    # Remove invalid characters for Windows/Unix filesystems
    # Keeps alphanumeric, spaces, hyphens, underscores, periods, brackets
    sanitized = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", filename)

    # Replace multiple spaces with single space
    sanitized = re.sub(r"\s+", " ", sanitized)

    # Strip leading/trailing whitespace
    sanitized = sanitized.strip()

    # Ensure filename isn't empty
    if not sanitized:
        sanitized = "untitled"

    return sanitized


__all__ = [
    "DownloadClient",
    "MultiFormatExporter",
    "SessionManager",
    "sanitize_filename",
]
