import logging
import sys
import os
from datetime import datetime, timezone

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs")

os.makedirs(LOG_DIR, exist_ok=True)


class StructuredFormatter(logging.Formatter):
    """JSON-style structured log formatter for production readability."""

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        level = record.levelname
        module = record.name
        msg = record.getMessage()
        line = f"{ts} | {level:<8} | {module}:{record.funcName}:{record.lineno} | {msg}"
        if record.exc_info and record.exc_info[0] is not None:
            line += "\n" + self.formatException(record.exc_info)
        return line


def get_logger(name: str) -> logging.Logger:
    """
    Returns a named logger with console + file handlers.
    Call once per module:  logger = get_logger(__name__)
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, LOG_LEVEL, logging.INFO))
    logger.propagate = False

    formatter = StructuredFormatter()

    # Console handler (stdout)
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.DEBUG)
    console.setFormatter(formatter)
    logger.addHandler(console)

    # File handler (rotating daily by name)
    log_file = os.path.join(LOG_DIR, "app.log")
    try:
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(
            log_file, maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8"
        )
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except Exception:
        logger.warning("Could not attach file handler for %s", log_file)

    return logger
