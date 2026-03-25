"""Tests for shared runtime logging configuration."""

from __future__ import annotations

import logging
from pathlib import Path

from logic import logging_config


def clear_root_handlers() -> None:
    """Remove existing root handlers so tests can assert exact logging setup."""
    root_logger = logging.getLogger()
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)
        handler.close()


def test_configure_logging_uses_single_app_log_file(tmp_path, monkeypatch):
    """Runtime logging should use one file-backed app log rather than rotated siblings."""
    logs_dir = tmp_path / "logs"
    app_log_path = logs_dir / "app.log"
    monkeypatch.setattr(logging_config, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(logging_config, "APP_LOG_PATH", app_log_path)
    clear_root_handlers()

    configured_path = logging_config.configure_logging()

    file_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if logging_config.is_app_file_handler(handler)
    ]
    assert configured_path == app_log_path
    assert len(file_handlers) == 1
    assert Path(file_handlers[0].baseFilename) == app_log_path


def test_configure_logging_reuses_existing_app_file_handler(tmp_path, monkeypatch):
    """Repeated configuration should not accumulate duplicate file handlers."""
    logs_dir = tmp_path / "logs"
    app_log_path = logs_dir / "app.log"
    monkeypatch.setattr(logging_config, "LOGS_DIR", logs_dir)
    monkeypatch.setattr(logging_config, "APP_LOG_PATH", app_log_path)
    clear_root_handlers()

    logging_config.configure_logging()
    logging_config.configure_logging()

    file_handlers = [
        handler
        for handler in logging.getLogger().handlers
        if logging_config.is_app_file_handler(handler)
    ]
    assert len(file_handlers) == 1
