"""Entry point for the MangaDex downloader CLI application."""

import argparse

from .app import MangaDexDownloaderApp


def main():
    """Run the MangaDex downloader application."""
    parser = argparse.ArgumentParser(
        description="Download manga from MangaDex and other providers"
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

    # run_app(config)
    app = MangaDexDownloaderApp()
    app.run()


if __name__ == "__main__":
    main()
