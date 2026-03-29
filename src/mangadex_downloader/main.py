"""Entry point for the MangaDex downloader CLI application."""

from .app import MangaDexDownloaderApp
from .utils.logger import setup_logging


def main():
    """Run the MangaDex downloader application."""
    setup_logging()
    app = MangaDexDownloaderApp()
    app.run()


if __name__ == "__main__":
    main()
