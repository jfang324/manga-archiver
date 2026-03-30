from argparse import ArgumentParser, ArgumentTypeError, Namespace

from ..constants.defaults import (
    DEFAULT_DOWNLOAD_RATE_LIMIT,
    DEFAULT_DOWNLOAD_WORKERS,
    DEFAULT_MERGE_WORKERS,
    DEFAULT_RESOLVE_RATE_LIMIT,
    DEFAULT_RESOLVE_WORKERS,
)


def positive_int(value: str) -> int:
    try:
        n = int(value)
    except ValueError as e:
        raise ArgumentTypeError(f"invalid integer value: {value}") from e

    if n < 1:
        raise ArgumentTypeError(f"must be at least 1, got {n}")

    return n


def create_parser() -> ArgumentParser:
    parser = ArgumentParser(
        description="MangaDex Downloader - Download manga from MangaDex"
    )

    parser.add_argument(
        "--resolve-workers",
        type=positive_int,
        default=DEFAULT_RESOLVE_WORKERS,
        help="Number of workers retrieving download resources (default: 5)",
    )

    parser.add_argument(
        "--download-workers",
        type=positive_int,
        default=DEFAULT_DOWNLOAD_WORKERS,
        help="Number of workers downloading images (default: 5)",
    )

    parser.add_argument(
        "--merge-workers",
        type=positive_int,
        default=DEFAULT_MERGE_WORKERS,
        help="Number of workers merging images into an output format (default: 5)",
    )

    parser.add_argument(
        "--resolve-rate-limit",
        type=positive_int,
        default=DEFAULT_RESOLVE_RATE_LIMIT,
        help="Global rate limit for resolve workers (default: 5)",
    )

    parser.add_argument(
        "--download-rate-limit",
        type=positive_int,
        default=DEFAULT_DOWNLOAD_RATE_LIMIT,
        help="Global rate limit for download workers (default: 5)",
    )

    return parser


def parse_args() -> Namespace:
    parser = create_parser()

    return parser.parse_args()
