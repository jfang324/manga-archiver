"""Unit tests for exception classes."""

import pytest

from src.mangadex_downloader.integrations.exceptions import (
    ApiError,
    DownloadError,
    MangaDexError,
    NotFoundError,
    RateLimitError,
)


class TestMangaDexError:
    """Test MangaDexError base exception."""

    def test_can_be_raised(self):
        """Test that MangaDexError can be raised and caught."""
        with pytest.raises(MangaDexError):
            raise MangaDexError("test error")

    def test_inherits_from_exception(self):
        """Test that MangaDexError inherits from Exception."""
        error = MangaDexError("test")
        assert isinstance(error, Exception)

    def test_message_is_stored(self):
        """Test that error message is preserved."""
        error = MangaDexError("test message")
        assert str(error) == "test message"


class TestNotFoundError:
    """Test NotFoundError exception."""

    def test_inherits_from_mangadex_error(self):
        """Test that NotFoundError inherits from MangaDexError."""
        error = NotFoundError("not found")
        assert isinstance(error, MangaDexError)

    def test_can_be_caught_as_mangadex_error(self):
        """Test that NotFoundError can be caught as MangaDexError."""
        with pytest.raises(MangaDexError):
            raise NotFoundError("test")

    def test_message_is_stored(self):
        """Test that error message is preserved."""
        error = NotFoundError("resource not found")
        assert str(error) == "resource not found"


class TestRateLimitError:
    """Test RateLimitError exception."""

    def test_inherits_from_mangadex_error(self):
        """Test that RateLimitError inherits from MangaDexError."""
        error = RateLimitError("rate limited")
        assert isinstance(error, MangaDexError)

    def test_can_be_caught_as_mangadex_error(self):
        """Test that RateLimitError can be caught as MangaDexError."""
        with pytest.raises(MangaDexError):
            raise RateLimitError("test")

    def test_message_is_stored(self):
        """Test that error message is preserved."""
        error = RateLimitError("rate limit exceeded")
        assert str(error) == "rate limit exceeded"


class TestApiError:
    """Test ApiError exception."""

    def test_inherits_from_mangadex_error(self):
        """Test that ApiError inherits from MangaDexError."""
        error = ApiError("api error")
        assert isinstance(error, MangaDexError)

    def test_can_be_caught_as_mangadex_error(self):
        """Test that ApiError can be caught as MangaDexError."""
        with pytest.raises(MangaDexError):
            raise ApiError("test")

    def test_message_is_stored(self):
        """Test that error message is preserved."""
        error = ApiError("api request failed")
        assert str(error) == "api request failed"


class TestDownloadError:
    """Test DownloadError exception."""

    def test_inherits_from_exception(self):
        """Test that DownloadError inherits from Exception."""
        error = DownloadError("download failed")
        assert isinstance(error, Exception)

    def test_can_be_raised(self):
        """Test that DownloadError can be raised."""
        with pytest.raises(DownloadError):
            raise DownloadError("test")

    def test_message_is_stored(self):
        """Test that error message is preserved."""
        error = DownloadError("download failed")
        assert str(error) == "download failed"


class TestExceptionHierarchy:
    """Test exception class hierarchy."""

    def test_all_mangadex_errors_inherit_base(self):
        """Test that all custom errors inherit from MangaDexError."""
        errors = [NotFoundError, RateLimitError, ApiError]
        for error_class in errors:
            error = error_class("test")
            assert isinstance(error, MangaDexError)

    def test_error_catching_priority(self):
        """Test that specific errors can be caught before generic ones."""
        try:
            raise NotFoundError("specific error")
        except NotFoundError as e:
            assert str(e) == "specific error"
        except MangaDexError:
            pytest.fail("Should have caught as NotFoundError first")
