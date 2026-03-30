import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.path.expanduser("~/.mangadex-downloader/logs"))


def setup_logging() -> None:
    """
    Configure application logging with time-based rotation.

    Creates two log files with daily rotation:
    - debug.log: All DEBUG and above messages
    - error.log: Only ERROR and above messages

    Keeps 7 days of log history (auto-deletes older logs).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    debug_handler = TimedRotatingFileHandler(
        LOG_DIR / "debug.log",
        when="midnight",
        interval=1,
        backupCount=7,
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )

    error_handler = TimedRotatingFileHandler(
        LOG_DIR / "error.log",
        when="midnight",
        interval=1,
        backupCount=7,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[debug_handler, error_handler])
