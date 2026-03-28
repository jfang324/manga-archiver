import logging
from logging.handlers import RotatingFileHandler


def setup_logging() -> None:
    """
    Configure application logging with file rotation.

    Creates two log files:
    - debug.log: All DEBUG and above messages
    - error.log: Only ERROR and above messages
    """
    debug_handler = RotatingFileHandler(
        "debug.log",
        maxBytes=5_000_000,
        backupCount=3,
    )
    debug_handler.setLevel(logging.DEBUG)
    debug_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    error_handler = RotatingFileHandler(
        "error.log",
        maxBytes=5_000_000,
        backupCount=5,
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(
        logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    )

    logging.basicConfig(level=logging.DEBUG, handlers=[debug_handler, error_handler])
