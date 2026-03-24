"""Database structure and generated data tests."""

import json
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


def test_generated_data_loads_correctly(test_database_path):
    """The generated test database should include buyer pledges and farms."""
    buyer_pledges = get_all_buyer_pledges()
    farms = get_all_farms()

    assert buyer_pledges
    assert len(farms) == 12


def test_foreign_keys_are_valid(test_database_path):
    """Generated records should satisfy all foreign key constraints."""
    with sqlite3.connect(test_database_path) as connection:
        failures = connection.execute("PRAGMA foreign_key_check").fetchall()

    assert failures == []


def test_buyer_pledge_quantities_are_positive(test_database_path):
    """Buyer pledge quantities should always be positive."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_count = connection.execute(
            "SELECT COUNT(*) FROM buyer_pledges WHERE quantity_kg <= 0"
        ).fetchone()[0]

    assert invalid_count == 0


def test_farmer_pledge_quantities_are_positive(test_database_path):
    """Farmer pledge quantities should always be positive."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_count = connection.execute(
            "SELECT COUNT(*) FROM farmer_pledges WHERE quantity_kg <= 0"
        ).fetchone()[0]

    assert invalid_count == 0


def test_allocations_never_exceed_buyer_demand(test_database_path):
    """Total allocated quantity should not exceed any buyer pledge quantity."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    bp.buyer_pledge_id,
                    bp.quantity_kg,
                    COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity
                FROM buyer_pledges AS bp
                LEFT JOIN pledge_allocations AS pa
                    ON bp.buyer_pledge_id = pa.buyer_pledge_id
                GROUP BY bp.buyer_pledge_id, bp.quantity_kg
                HAVING allocated_quantity > bp.quantity_kg
            )
            """
        ).fetchone()[0]

    assert invalid_count == 0


def test_allocations_never_exceed_farmer_supply(test_database_path):
    """Total allocated quantity should not exceed any farmer pledge quantity."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT
                    fp.farmer_pledge_id,
                    fp.quantity_kg,
                    COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity
                FROM farmer_pledges AS fp
                LEFT JOIN pledge_allocations AS pa
                    ON fp.farmer_pledge_id = pa.farmer_pledge_id
                GROUP BY fp.farmer_pledge_id, fp.quantity_kg
                HAVING allocated_quantity > fp.quantity_kg
            )
            """
        ).fetchone()[0]

    assert invalid_count == 0


def test_buyer_pledge_statuses_match_allocation_totals(test_database_path):
    """Buyer pledge statuses should align with aggregated allocation quantities."""
    with sqlite3.connect(test_database_path) as connection:
        rows = connection.execute(
            """
            SELECT
                bp.buyer_pledge_id,
                bp.quantity_kg,
                bp.pledge_status,
                COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity
            FROM buyer_pledges AS bp
            LEFT JOIN pledge_allocations AS pa
                ON bp.buyer_pledge_id = pa.buyer_pledge_id
            GROUP BY bp.buyer_pledge_id, bp.quantity_kg, bp.pledge_status
            """
        ).fetchall()

    for _, quantity_kg, pledge_status, allocated_quantity in rows:
        expected_status = (
            "open"
            if allocated_quantity == 0
            else "fulfilled"
            if allocated_quantity == quantity_kg
            else "partial"
        )
        assert pledge_status == expected_status


def test_generated_data_contains_open_partial_and_fulfilled_buyer_pledges(test_database_path):
    """Generated data should include all buyer allocation states."""
    with sqlite3.connect(test_database_path) as connection:
        status_counts = dict(
            connection.execute(
                "SELECT pledge_status, COUNT(*) FROM buyer_pledges GROUP BY pledge_status"
            ).fetchall()
        )

    assert status_counts.get("open", 0) > 0
    assert status_counts.get("partial", 0) > 0
    assert status_counts.get("fulfilled", 0) > 0


def test_generated_data_contains_optional_null_fields(test_database_path):
    """Generated data should include NULLs in optional fields."""
    with sqlite3.connect(test_database_path) as connection:
        buyer_price_nulls = connection.execute(
            "SELECT COUNT(*) FROM buyer_pledges WHERE target_price_per_kg IS NULL"
        ).fetchone()[0]
        farmer_price_nulls = connection.execute(
            "SELECT COUNT(*) FROM farmer_pledges WHERE asking_price_per_kg IS NULL"
        ).fetchone()[0]
        farmer_email_nulls = connection.execute(
            "SELECT COUNT(*) FROM farmer_accounts WHERE email IS NULL"
        ).fetchone()[0]
        input_log_pledge_nulls = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE farmer_pledge_id IS NULL"
        ).fetchone()[0]

    assert buyer_price_nulls > 0
    assert farmer_price_nulls > 0
    assert farmer_email_nulls > 0
    assert input_log_pledge_nulls > 0


def test_buyer_pledge_notes_are_valid_json(test_database_path):
    """Buyer pledge notes should contain valid JSON strings."""
    with sqlite3.connect(test_database_path) as connection:
        notes_values = connection.execute(
            "SELECT notes FROM buyer_pledges WHERE notes IS NOT NULL"
        ).fetchall()

    assert notes_values
    for (notes,) in notes_values:
        parsed = json.loads(notes)
        assert isinstance(parsed, dict)
        assert "priority" in parsed
        assert "organic_preference" in parsed


def test_deadlines_do_not_precede_creation_dates(test_database_path):
    """Buyer deadlines and farmer availability dates should not precede creation."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_buyer_dates = connection.execute(
            """
            SELECT COUNT(*)
            FROM buyer_pledges
            WHERE needed_by_date IS NOT NULL
              AND date(needed_by_date) < date(created_at)
            """
        ).fetchone()[0]
        invalid_farmer_dates = connection.execute(
            """
            SELECT COUNT(*)
            FROM farmer_pledges
            WHERE available_from_date IS NOT NULL
              AND date(available_from_date) < date(created_at)
            """
        ).fetchone()[0]

    assert invalid_buyer_dates == 0
    assert invalid_farmer_dates == 0


def test_input_logs_reference_matching_farmer_when_pledge_is_present(test_database_path):
    """Input log pledge references should belong to the same farmer account."""
    with sqlite3.connect(test_database_path) as connection:
        invalid_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM farm_input_logs AS fil
            INNER JOIN farmer_pledges AS fp
                ON fil.farmer_pledge_id = fp.farmer_pledge_id
            WHERE fil.farmer_pledge_id IS NOT NULL
              AND fil.farmer_account_id != fp.farmer_account_id
            """
        ).fetchone()[0]

    assert invalid_count == 0
