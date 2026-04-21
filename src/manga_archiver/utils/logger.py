import logging
import os
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

LOG_DIR = Path(os.path.expanduser("~/.manga-archiver/logs"))


def setup_logging() -> None:
    """Configure application logging with time-based rotation.

    Creates three log files with daily rotation:
    - debug.log: All DEBUG and above messages
    - error.log: Only ERROR and above messages
    - info.log: INFO and above messages (for benchmark output)

    Keeps 2 days of log history (auto-deletes older logs).
    """
    LOG_DIR.mkdir(parents=True, exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.handlers.clear()

    debug_handler = TimedRotatingFileHandler(
        LOG_DIR / "debug.log",
        when="midnight",
        interval=1,
        backupCount=2,
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(debug_handler)

    error_handler = TimedRotatingFileHandler(
        LOG_DIR / "error.log",
        when="midnight",
        interval=1,
        backupCount=2,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(error_handler)

    info_handler = TimedRotatingFileHandler(
        LOG_DIR / "info.log",
        when="midnight",
        interval=1,
        backupCount=2,
    )
    info_handler.setLevel(logging.INFO)
    info_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )
    root_logger.addHandler(info_handler)
