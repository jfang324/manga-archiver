import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_PROVIDER_RATE_LIMIT,
    DEFAULT_QUEUE_SIZE,
    DEFAULT_RESOLVE_WORKERS,
)
from .presets import get_preset_names
from .subcommands import add_auth_parser, add_list_parser, add_migrate_parser
from .validators import positive_int

FALLBACK_VERSION = "v0.0.0"
MANUAL_TUNING_OPTIONS = (
    "--resolve-workers",
    "--download-workers",
    "--merge-workers",
    "--resolve-rate-limit",
    "--download-rate-limit",
    "--queue-size",
)


def _get_package_version() -> str:
    """Return the installed package version string."""
    try:
        return f"v{package_version('manga-archiver')}"
    except PackageNotFoundError:
        return FALLBACK_VERSION


def _build_parser() -> ArgumentParser:
    """Create the command-line parser and command-specific subparsers."""
    parser = ArgumentParser(
        description="Manga Archiver - Download manga from sources like MangaDex and AllManga locally or directly to your Google Drive",
        formatter_class=lambda prog: RawTextHelpFormatter(prog, max_help_position=50),
        allow_abbrev=False,
    )
    subparsers = parser.add_subparsers(dest="command", title="commands", metavar="")

    add_auth_parser(subparsers)
    add_migrate_parser(subparsers)
    add_list_parser(subparsers)

    parser.add_argument(
        "--version",
        action="version",
        version=_get_package_version(),
        help="Show the current version and exit",
    )

    parser.add_argument(
        "--preset",
        choices=get_preset_names(),
        help="Run with a preset configuration",
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
        "--headless",
        action="store_true",
        help="Run backlog processing without launching the Textual UI (requires --archive --backlog)",
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
    raw_args = sys.argv[1:] if argv is None else argv
    args = parser.parse_args(argv)

    if args.preset is not None:
        raw_option_names = {raw_arg.split("=", maxsplit=1)[0] for raw_arg in raw_args}
        conflicting_options = [
            option for option in MANUAL_TUNING_OPTIONS if option in raw_option_names
        ]
        if conflicting_options:
            options = ", ".join(conflicting_options)
            parser.error(f"--preset cannot be combined with manual tuning options: {options}")

    if args.headless and (not args.archive or not args.backlog):
        parser.error("--headless requires --archive and --backlog")

    return args
