from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from collections.abc import Sequence
from importlib.metadata import version

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_PROVIDER_RATE_LIMIT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_RESOLVE_WORKERS,
)
from .subcommands import add_auth_parser, add_migrate_parser
from .validators import positive_int


def _build_parser() -> ArgumentParser:
    """Create the command-line parser and command-specific subparsers."""
    parser = ArgumentParser(
        description="Manga Archiver - Download manga from sources like MangaDex and AllManga locally or directly to your Google Drive",
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=50),
    )
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="")

    add_auth_parser(subparsers)
    add_migrate_parser(subparsers)

    parser.add_argument(
        "--version",
        action="version",
        version=f"v{version('manga-archiver')}",
        help="Show the current version and exit",
    )

    parser.add_argument(
        "--resolve-workers",
        type=positive_int,
        default=DEFAULT_RESOLVE_WORKERS,
        help=f"Number of workers retrieving download resources (default: {DEFAULT_RESOLVE_WORKERS})",
    )

    parser.add_argument(
        "--download-workers",
        type=positive_int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help=f"Number of workers downloading images (default: {DEFAULT_DOWNLOAD_WORKERS})",
    )

    parser.add_argument(
        "--merge-workers",
        type=positive_int,
        default=DEFAULT_MERGE_WORKERS,
        help=f"Number of workers merging images into an output format (default: {DEFAULT_MERGE_WORKERS})",
    )

    parser.add_argument(
        "--resolve-rate-limit",
        type=positive_int,
        default=DEFAULT_PROVIDER_RATE_LIMIT,
        help=f"Per-provider rate limit for resolve operations (default: {DEFAULT_PROVIDER_RATE_LIMIT})",
    )

    parser.add_argument(
        "--download-rate-limit",
        type=positive_int,
        default=DEFAULT_DOWNLOAD_RATE_LIMIT,
        help=f"Per-provider rate limit for download operations (default: {DEFAULT_DOWNLOAD_RATE_LIMIT})",
    )

    parser.add_argument(
        "--queue-size",
        type=positive_int,
        default=DEFAULT_QUEUE_SIZE,
        help=f"Queue size for data-heavy job queues (default: {DEFAULT_QUEUE_SIZE})",
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

    parser.add_argument(
        "--auto-exit",
        action="store_true",
        help="Automatically exit when all jobs are complete",
    )

    return parser


def parse_args(argv: Sequence[str] | None = None) -> Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list to parse. When omitted, argparse reads sys.argv.

    Returns:
        Namespace: Parsed command-line arguments
    """
    parser = _build_parser()
    return parser.parse_args(argv)
