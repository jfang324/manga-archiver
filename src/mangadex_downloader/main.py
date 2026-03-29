from .app import MangaDexDownloaderApp
from .utils import setup_logging


def main():
    setup_logging()
    app = MangaDexDownloaderApp()
    app.run()


if __name__ == "__main__":
    main()
