"""Utility functions for the MangaDex downloader."""

import re

from .downloader import DownloadClient
from .pdf_generator import PdfGenerator
from .session_manager import SessionManager


def sanitize_filename(filename: str) -> str:
    """Sanitize a string to be used as a filename.

    Removes or replaces characters that are invalid or problematic in filenames.

    :param filename: The filename to sanitize
    :return: The sanitized filename
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
    "PdfGenerator",
    "SessionManager",
    "sanitize_filename",
]
