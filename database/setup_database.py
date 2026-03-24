"""Create the SQLite database schema for the agricultural coordination platform."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "app_data.db"
sys.path.insert(0, str(PROJECT_ROOT))

from logic.logging_config import configure_logging


logger = logging.getLogger(__name__)

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS buyer_accounts (
    buyer_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS buyer_pledges (
    buyer_pledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_account_id INTEGER NOT NULL,
    crop_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    target_price_per_kg REAL,
    needed_by_date TEXT,
    pledge_status TEXT NOT NULL DEFAULT 'open',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_account_id) REFERENCES buyer_accounts (buyer_account_id)
);

CREATE TABLE IF NOT EXISTS farmer_accounts (
    farmer_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_name TEXT NOT NULL,
    farmer_name TEXT NOT NULL,
    county TEXT,
    region TEXT,
    email TEXT,
    phone TEXT,
    total_hectares REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS farmer_pledges (
    farmer_pledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_account_id INTEGER NOT NULL,
    crop_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    asking_price_per_kg REAL,
    available_from_date TEXT,
    pledge_status TEXT NOT NULL DEFAULT 'available',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_account_id) REFERENCES farmer_accounts (farmer_account_id)
);

CREATE TABLE IF NOT EXISTS pledge_allocations (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_pledge_id INTEGER NOT NULL,
    farmer_pledge_id INTEGER NOT NULL,
    allocated_quantity_kg REAL NOT NULL,
    allocation_status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_pledge_id) REFERENCES buyer_pledges (buyer_pledge_id),
    FOREIGN KEY (farmer_pledge_id) REFERENCES farmer_pledges (farmer_pledge_id)
);

CREATE TABLE IF NOT EXISTS farm_input_logs (
    input_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_account_id INTEGER NOT NULL,
    farmer_pledge_id INTEGER,
    input_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    log_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_account_id) REFERENCES farmer_accounts (farmer_account_id),
    FOREIGN KEY (farmer_pledge_id) REFERENCES farmer_pledges (farmer_pledge_id)
);
"""


def initialise_database(database_path: Path = DATABASE_PATH) -> Path:
    """Create the database file and ensure all tables exist."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(SCHEMA_SQL)
        connection.commit()

    return database_path


def main() -> None:
    """Create the database schema and print the resulting path."""
    log_path = configure_logging()
    logger.info("Schema setup started; logging to %s", log_path)
    database_path = initialise_database()
    logger.info("Schema setup complete for %s", database_path)
    print(f"Database schema ready: {database_path}")


if __name__ == "__main__":
    main()
