"""Database structure and sample data tests."""

import sqlite3

from logic.database_helpers import get_all_buyer_pledges, get_all_farms


EXPECTED_TABLES = {
    "buyer_accounts",
    "buyer_pledges",
    "farmer_accounts",
    "farmer_pledges",
    "pledge_allocations",
    "farm_input_logs",
}


def test_expected_tables_exist(test_database_path):
    """All required tables should be created in the database."""
    with sqlite3.connect(test_database_path) as connection:
        rows = connection.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table'
            """
        ).fetchall()

    table_names = {row[0] for row in rows}
    assert EXPECTED_TABLES.issubset(table_names)


def test_sample_data_loads_correctly(test_database_path):
    """The demo database should include initial buyer pledges and farms."""
    buyer_pledges = get_all_buyer_pledges()
    farms = get_all_farms()

    assert len(buyer_pledges) == 2
    assert len(farms) == 4
