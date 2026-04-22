from argparse import ArgumentParser, Namespace, RawTextHelpFormatter

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_PROVIDER_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
)
from .subcommands import add_auth_parser, add_migrate_parser
from .validators import positive_int


def _build_parser() -> tuple[ArgumentParser, ArgumentParser, ArgumentParser]:
    """Create the command-line parser and command-specific subparsers."""
    parser = ArgumentParser(
        description="Manga Archiver - Download manga from sources like MangaDex and AllManga locally or directly to your Google Drive",
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=50),
    )
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="")

    auth_parser = add_auth_parser(subparsers)
    migrate_parser = add_migrate_parser(subparsers)

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

    return parser, auth_parser, migrate_parser


def parse_args() -> Namespace:
    """Parse command-line arguments.

    Returns:
        Namespace: Parsed command-line arguments
    """
    parser, auth_parser, migrate_parser = _build_parser()
    args = parser.parse_args()

    if args.command == "auth" and args.auth_command is None:
        auth_parser.error("please specify a subcommand: login or logout")

    if args.command == "migrate" and args.migrate_system is None:
        migrate_parser.error("please specify a subcommand: database or google-drive")

    return args
