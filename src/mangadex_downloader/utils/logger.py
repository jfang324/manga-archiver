import logging
from logging.handlers import TimedRotatingFileHandler


def setup_logging() -> None:
    """
    Configure application logging with time-based rotation.

    Creates two log files with daily rotation:
    - debug.log: All DEBUG and above messages
    - error.log: Only ERROR and above messages

    Keeps 7 days of log history (auto-deletes older logs).
    """
    debug_handler = TimedRotatingFileHandler(
        "debug.log",
        when="midnight",
        interval=1,
        backupCount=7,
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )

    error_handler = TimedRotatingFileHandler(
        "error.log",
        when="midnight",
        interval=1,
        backupCount=7,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s - [%(name)s] - %(levelname)s - %(message)s")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[debug_handler, error_handler])
