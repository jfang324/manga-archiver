"""Entry point for the MangaDex downloader CLI application."""

import argparse

from .cli import run_app
from .cli.app import Config


def main():
    """Run the MangaDex downloader application."""
    parser = argparse.ArgumentParser(
        description="Download manga chapters from MangaDex"
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=10,
        help="Number of items to display per page (default: 10)",
    )
    parser.add_argument(
        "--quality",
        type=int,
        default=75,
        help="PDF quality 1-100 (default: 75)",
    )
    parser.add_argument(
        "--optimize",
        action="store_true",
        help="Optimize PDF file size",
    )
    parser.add_argument(
        "--data-saver",
        action="store_true",
        help="Download lower quality images (data-saver mode)",
    )

    args = parser.parse_args()

    config = Config(
        page_size=args.page_size,
        quality=args.quality,
        optimize=args.optimize,
        data_saver=args.data_saver,
    )

    run_app(config)


if __name__ == "__main__":
    main()
