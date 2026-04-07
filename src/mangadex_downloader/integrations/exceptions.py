class ApiError(Exception):
    """Raised for general API errors."""


class NotFoundError(ApiError):
    """Raised when a requested resource is not found (404)."""


class RateLimitError(ApiError):
    """Raised when the API rate limit is exceeded (429)."""
