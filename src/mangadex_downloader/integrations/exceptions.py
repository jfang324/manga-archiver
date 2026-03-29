class MangaDexError(Exception):
    """Base exception for all MangaDex API errors."""


class NotFoundError(MangaDexError):
    """Raised when a requested resource is not found (404)."""


class RateLimitError(MangaDexError):
    """Raised when the API rate limit is exceeded (429)."""


class ApiError(MangaDexError):
    """Raised for general API errors."""


class DownloadError(Exception):
    """Raised when an image download fails."""
