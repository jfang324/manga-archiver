"""Database migration version constants."""

DEFAULT_VERSION = "v1.1.0"  # This should be synced up with the latest version of the app
MIN_DATABASE_VERSION = "v1.1.0"  # This needs to be changes when schema changes are made
MIN_GOOGLE_DRIVE_VERSION = None  # This needs to be changes when schema changes are made

__all__ = [
    "DEFAULT_VERSION",
    "MIN_DATABASE_VERSION",
    "MIN_GOOGLE_DRIVE_VERSION",
]
