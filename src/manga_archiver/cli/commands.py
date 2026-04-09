from argparse import ArgumentParser, ArgumentTypeError, Namespace, RawTextHelpFormatter

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_RESOLVE_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
)


def _positive_int(value: str) -> int:
    """Validate that a string is a positive integer."""
    try:
        n = int(value)
    except ValueError as e:
        raise ArgumentTypeError(f"invalid integer value: {value}") from e

    if n < 1:
        raise ArgumentTypeError(f"must be at least 1, got {n}")

    return n


def create_parser() -> ArgumentParser:
    """Create the command-line argument parser.

    Returns:
        ArgumentParser: Configured ArgumentParser instance
    """
    parser = ArgumentParser(
        description="Manga Archiver - Download manga from sources like MangaDex directly to your Google Drive",
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=50),
    )
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="")

    auth_parser = subparsers.add_parser("auth", help="Google Drive authentication")
    auth_subparsers = auth_parser.add_subparsers(dest="auth_command", required=True)

    auth_subparsers.add_parser("login", help="Log in to Google Drive")
    auth_subparsers.add_parser("logout", help="Log out of Google Drive")

    parser.add_argument(
        "--resolve-workers",
        type=_positive_int,
        default=DEFAULT_RESOLVE_WORKERS,
        help=f"Number of workers retrieving download resources (default: {DEFAULT_RESOLVE_WORKERS})",
    )

    parser.add_argument(
        "--download-workers",
        type=_positive_int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help=f"Number of workers downloading images (default: {DEFAULT_DOWNLOAD_WORKERS})",
    )

    parser.add_argument(
        "--merge-workers",
        type=_positive_int,
        default=DEFAULT_MERGE_WORKERS,
        help=f"Number of workers merging images into an output format (default: {DEFAULT_MERGE_WORKERS})",
    )

    parser.add_argument(
        "--resolve-rate-limit",
        type=_positive_int,
        default=DEFAULT_RESOLVE_RATE_LIMIT,
        help=f"Global rate limit for resolve workers (default: {DEFAULT_RESOLVE_RATE_LIMIT})",
    )

    parser.add_argument(
        "--download-rate-limit",
        type=_positive_int,
        default=DEFAULT_DOWNLOAD_RATE_LIMIT,
        help=f"Global rate limit for download workers (default: {DEFAULT_DOWNLOAD_RATE_LIMIT})",
    )

    parser.add_argument(
        "--archive",
        action="store_true",
        help="Enable archive mode (upload to Google Drive instead of local save)",
    )

    parser.add_argument(
        "--benchmark",
        action="store_true",
        help="Enable performance benchmarking",
    )

    parser.add_argument(
        "--backlog",
        action="store_true",
        help="Sync favorites with Google Drive and download missing chapters",
    )

    return parser


def parse_args() -> Namespace:
    """Parse command-line arguments.

    Returns:
        Namespace: Parsed command-line arguments
    """
    parser = create_parser()

    return parser.parse_args()
