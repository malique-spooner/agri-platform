"""Database helper functions for retrieving application data."""

from __future__ import annotations

import os
from pathlib import Path
import sqlite3
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "database" / "app_data.db"


def get_database_path() -> Path:
    """Return the configured database path, defaulting to the local demo database."""
    return Path(os.environ.get("AGRI_PLATFORM_DB_PATH", DEFAULT_DATABASE_PATH))


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection configured to return rows by column name."""
    connection = sqlite3.connect(get_database_path())
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert SQLite row objects to plain dictionaries."""
    return [dict(row) for row in rows]


def get_all_buyer_pledges() -> list[dict[str, Any]]:
    """Return all buyer pledges with the buyer organisation name attached."""
    query = """
        SELECT
            bp.buyer_pledge_id,
            ba.organisation_name,
            bp.crop_type,
            bp.quantity_kg,
            bp.target_price_per_kg,
            bp.needed_by_date,
            bp.pledge_status,
            bp.notes
        FROM buyer_pledges AS bp
        INNER JOIN buyer_accounts AS ba
            ON bp.buyer_account_id = ba.buyer_account_id
        ORDER BY bp.needed_by_date, bp.buyer_pledge_id
    """

    with get_connection() as connection:
        rows = connection.execute(query).fetchall()

    return rows_to_dicts(rows)


def get_all_farms() -> list[dict[str, Any]]:
    """Return all farmer accounts for the farm directory."""
    query = """
        SELECT
            farmer_account_id,
            farm_name,
            farmer_name,
            county,
            region,
            email,
            phone,
            total_hectares
        FROM farmer_accounts
        ORDER BY farm_name
    """

    with get_connection() as connection:
        rows = connection.execute(query).fetchall()

    return rows_to_dicts(rows)


def get_farm_by_id(farm_id: int) -> dict[str, Any] | None:
    """Return a single farm profile by its identifier."""
    query = """
        SELECT
            farmer_account_id,
            farm_name,
            farmer_name,
            county,
            region,
            email,
            phone,
            total_hectares
        FROM farmer_accounts
        WHERE farmer_account_id = ?
    """

    with get_connection() as connection:
        row = connection.execute(query, (farm_id,)).fetchone()

    return dict(row) if row else None


def get_farmer_pledges_for_crop(crop_type: str) -> list[dict[str, Any]]:
    """Return farmer pledges that match a requested crop type."""
    query = """
        SELECT
            fp.farmer_pledge_id,
            fp.crop_type,
            fp.quantity_kg,
            fp.asking_price_per_kg,
            fp.available_from_date,
            fp.pledge_status,
            fa.farm_name,
            fa.farmer_name
        FROM farmer_pledges AS fp
        INNER JOIN farmer_accounts AS fa
            ON fp.farmer_account_id = fa.farmer_account_id
        WHERE fp.crop_type = ?
        ORDER BY fp.available_from_date, fp.farmer_pledge_id
    """

    with get_connection() as connection:
        rows = connection.execute(query, (crop_type,)).fetchall()

    return rows_to_dicts(rows)
