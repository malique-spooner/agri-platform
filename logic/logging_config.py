"""Central logging configuration for the application."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
APP_LOG_PATH = LOGS_DIR / "app.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure shared application logging and return the log file path."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    APP_LOG_PATH.touch(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        if isinstance(handler, RotatingFileHandler) and Path(
            getattr(handler, "baseFilename", "")
        ) != APP_LOG_PATH:
            root_logger.removeHandler(handler)
            handler.close()

    file_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, RotatingFileHandler)
            and Path(getattr(handler, "baseFilename", "")) == APP_LOG_PATH
        ),
        None,
    )
    if file_handler is None:
        file_handler = RotatingFileHandler(
            APP_LOG_PATH,
            maxBytes=1_048_576,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and not isinstance(handler, RotatingFileHandler)
        ),
        None,
    )
    if console_handler is None:
        console_handler = logging.StreamHandler()
        root_logger.addHandler(console_handler)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    logging.getLogger("werkzeug").setLevel(level)
    logging.captureWarnings(True)

    return APP_LOG_PATH
