from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from collections.abc import Sequence
from importlib.metadata import PackageNotFoundError
from importlib.metadata import version as package_version

from .presets import get_preset_names
from .subcommands import (
    add_auth_parser,
    add_config_parser,
    add_health_parser,
    add_list_parser,
    add_migrate_parser,
)

FALLBACK_VERSION = "v0.0.0"


def parse_args(argv: Sequence[str] | None = None) -> Namespace:
    """Parse command-line arguments.

    Args:
        argv: Optional argument list to parse. When omitted, argparse reads sys.argv.

    Returns:
        Namespace: Parsed command-line arguments
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    if args.headless and (not args.archive or not args.backlog):
        parser.error("--headless requires --archive and --backlog")

    return args


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
    add_health_parser(subparsers)
    add_config_parser(subparsers)

    parser.add_argument(
        "--version",
        action="version",
        version=_get_package_version(),
        help="Show the current version and exit",
    )

    parser.add_argument(
        "--preset",
        choices=get_preset_names(),
        default="default",
        help="Run with a preset configuration",
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


def _get_package_version() -> str:
    """Return the installed package version string."""
    try:
        return f"v{package_version('manga-archiver')}"
    except PackageNotFoundError:
        return FALLBACK_VERSION
