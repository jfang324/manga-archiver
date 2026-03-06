"""Custom exceptions for API integrations."""


class MangaDexError(Exception):
    """Base exception for MangaDex API errors."""

    pass


class NotFoundError(MangaDexError):
    """Raised when a requested resource is not found."""

    pass


class RateLimitError(MangaDexError):
    """Raised when rate limit is exceeded."""

    pass


class ApiError(MangaDexError):
    """Raised for general API errors."""

    pass


class DownloadError(Exception):
    """Raised when image download fails."""

    pass
