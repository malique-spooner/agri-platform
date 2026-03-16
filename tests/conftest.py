"""Shared pytest fixtures for the agricultural platform tests."""

from __future__ import annotations

from pathlib import Path
import sqlite3
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = PROJECT_ROOT / "database" / "create_tables.sql"
SAMPLE_DATA_PATH = PROJECT_ROOT / "database" / "sample_data.sql"
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app


def build_test_database(database_path: Path) -> None:
    """Create a fresh SQLite test database from the project SQL files."""
    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))
        connection.executescript(SAMPLE_DATA_PATH.read_text(encoding="utf-8"))
        connection.commit()


@pytest.fixture()
def test_database_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create and configure an isolated database path for a test."""
    database_path = tmp_path / "test_app_data.db"
    build_test_database(database_path)
    monkeypatch.setenv("AGRI_PLATFORM_DB_PATH", str(database_path))
    return database_path


@pytest.fixture()
def app(test_database_path: Path):
    """Create a Flask application configured for testing."""
    flask_app = create_app()
    flask_app.config.update(TESTING=True)
    return flask_app


@pytest.fixture()
def client(app):
    """Create a Flask test client."""
    return app.test_client()
