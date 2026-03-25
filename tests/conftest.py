"""Shared pytest fixtures for the agricultural platform tests."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
import sys

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from app import create_app
from database.generate_data import generate_dataset


def build_test_database(database_path: Path) -> None:
    """Create a fresh SQLite test database using deterministic synthetic data."""
    generate_dataset(
        SimpleNamespace(
            buyers=8,
            buyer_pledges_total=12,
            farmers=16,
            max_buyer_pledges=3,
            max_farmer_pledges=4,
            max_input_logs=8,
            seed=20260324,
            database_path=database_path,
        )
    )


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
