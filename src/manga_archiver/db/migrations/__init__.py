"""Database migration version constants."""

# Default constants represent the current version our systems get initialized with
DEFAULT_DATABASE_VERSION = "v1.1.0"
DEFAULT_GOOGLE_DRIVE_VERSION = "v1.1.0"

# Minimum constants represent the minimum version of the schemas we can work with
MIN_DATABASE_VERSION = "v1.1.0"
MIN_GOOGLE_DRIVE_VERSION = "v1.1.0"

LEGACY_VERSION = "v1.0.0"

__all__ = [
    "DEFAULT_DATABASE_VERSION",
    "DEFAULT_GOOGLE_DRIVE_VERSION",
    "MIN_DATABASE_VERSION",
    "MIN_GOOGLE_DRIVE_VERSION",
    "LEGACY_VERSION",
]
