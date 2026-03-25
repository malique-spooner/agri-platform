"""Central logging configuration for the application."""

from __future__ import annotations

import logging
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
APP_LOG_PATH = LOGS_DIR / "app.log"
LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def is_app_file_handler(handler: logging.Handler) -> bool:
    """Return whether a handler is the application's file-backed log handler."""
    return isinstance(handler, logging.FileHandler) and hasattr(handler, "baseFilename")


def configure_logging(level: int = logging.INFO) -> Path:
    """Configure shared application logging and return the single log file path."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    APP_LOG_PATH.touch(exist_ok=True)

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for handler in list(root_logger.handlers):
        if is_app_file_handler(handler) and Path(getattr(handler, "baseFilename", "")) != APP_LOG_PATH:
            root_logger.removeHandler(handler)
            handler.close()

    file_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if is_app_file_handler(handler) and Path(getattr(handler, "baseFilename", "")) == APP_LOG_PATH
        ),
        None,
    )
    if file_handler is None:
        file_handler = logging.FileHandler(APP_LOG_PATH, encoding="utf-8")
        file_handler.setLevel(level)
        root_logger.addHandler(file_handler)
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT))

    console_handler = next(
        (
            handler
            for handler in root_logger.handlers
            if isinstance(handler, logging.StreamHandler)
            and not is_app_file_handler(handler)
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
