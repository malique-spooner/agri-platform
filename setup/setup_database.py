"""Utility for creating the application database and loading demo data."""

from pathlib import Path
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_DIR = PROJECT_ROOT / "database"
DATABASE_PATH = DATABASE_DIR / "app_data.db"
SCHEMA_PATH = DATABASE_DIR / "create_tables.sql"
SAMPLE_DATA_PATH = DATABASE_DIR / "sample_data.sql"


def read_sql_file(file_path: Path) -> str:
    """Read an SQL file and return its contents as a string."""
    return file_path.read_text(encoding="utf-8")


def initialise_database(database_path: Path = DATABASE_PATH) -> None:
    """Create the database file and load the schema plus sample data."""
    DATABASE_DIR.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        connection.executescript(read_sql_file(SCHEMA_PATH))
        connection.executescript(read_sql_file(SAMPLE_DATA_PATH))
        connection.commit()


def main() -> None:
    """Run the database setup workflow."""
    initialise_database()
    print(f"Database setup complete: {DATABASE_PATH}")


if __name__ == "__main__":
    main()
