"""Database structure and generated data tests."""

from datetime import date
import json
import sqlite3

from logic.database_helpers import get_all_buyer_pledges, get_all_farms, persist_confirmed_allocation

SUPPORTED_AFRICAN_COUNTRIES = {
    "Kenya",
    "Uganda",
    "Zambia",
}

COUNTRY_COORDINATE_RANGES = {
    "Kenya": {"lat": (-4.75, 4.62), "lon": (33.91, 41.90)},
    "Uganda": {"lat": (-1.48, 4.23), "lon": (29.57, 35.04)},
    "Zambia": {"lat": (-18.08, -8.20), "lon": (21.99, 33.70)},
}

COUNTRY_COUNTIES = {
    "Kenya": {"Nakuru", "Kiambu", "Meru", "Machakos"},
    "Uganda": {"Wakiso", "Mbarara", "Gulu", "Mbale"},
    "Zambia": {"Lusaka", "Central", "Copperbelt", "Eastern"},
}


EXPECTED_TABLES = {
    "input_catalog",
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


def test_input_catalog_is_seeded(test_database_path):
    """The normalized input catalog should be populated for settings and matching logic."""
    with sqlite3.connect(test_database_path) as connection:
        entry_count = connection.execute("SELECT COUNT(*) FROM input_catalog").fetchone()[0]

    assert entry_count >= 8


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


def test_farm_input_logs_reference_the_normalized_catalog(test_database_path):
    """Every generated input log should point back to a standardized catalog entry."""
    with sqlite3.connect(test_database_path) as connection:
        missing_links = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE input_catalog_id IS NULL"
        ).fetchone()[0]

    assert missing_links == 0


def test_generated_farm_coordinates_are_in_supported_african_countries(test_database_path):
    """Generated farms should belong to supported African countries and valid coordinate ranges."""
    with sqlite3.connect(test_database_path) as connection:
        rows = connection.execute(
            "SELECT region, county, latitude, longitude FROM farmer_accounts"
        ).fetchall()

    assert rows
    for region, county, latitude, longitude in rows:
        assert region in SUPPORTED_AFRICAN_COUNTRIES
        assert county in COUNTRY_COUNTIES[region]
        assert latitude is not None
        assert longitude is not None
        bounds = COUNTRY_COORDINATE_RANGES[region]
        assert bounds["lat"][0] <= latitude <= bounds["lat"][1]
        assert bounds["lon"][0] <= longitude <= bounds["lon"][1]


def test_farm_directory_dataset_only_uses_three_supported_countries(test_database_path):
    """The demo dataset should stay inside the configured three-country operating region."""
    farms = get_all_farms()

    assert farms
    assert {farm["region"] for farm in farms} == SUPPORTED_AFRICAN_COUNTRIES


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
        assert "required_inputs" in parsed
        assert "blocked_inputs" in parsed
        assert isinstance(parsed["required_inputs"], list)
        assert isinstance(parsed["blocked_inputs"], list)


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


def test_generated_dates_stay_close_to_today_for_demo_use(test_database_path):
    """Deadlines, availability windows, and logs should stay near the current operating period."""
    today = date.today().isoformat()
    with sqlite3.connect(test_database_path) as connection:
        distant_buyer_dates = connection.execute(
            """
            SELECT COUNT(*)
            FROM buyer_pledges
            WHERE needed_by_date IS NOT NULL
              AND ABS(julianday(needed_by_date) - julianday(?)) > 90
            """,
            (today,),
        ).fetchone()[0]
        distant_farmer_dates = connection.execute(
            """
            SELECT COUNT(*)
            FROM farmer_pledges
            WHERE available_from_date IS NOT NULL
              AND ABS(julianday(available_from_date) - julianday(?)) > 90
            """,
            (today,),
        ).fetchone()[0]
        future_logs = connection.execute(
            """
            SELECT COUNT(*)
            FROM farm_input_logs
            WHERE date(log_date) > date(?)
            """,
            (today,),
        ).fetchone()[0]

    assert distant_buyer_dates == 0
    assert distant_farmer_dates == 0
    assert future_logs == 0


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


def test_generated_dataset_contains_dense_crop_input_history(test_database_path):
    """Most farmer pledges should have multiple linked logs so crop pages are informative."""
    with sqlite3.connect(test_database_path) as connection:
        linked_log_count = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE farmer_pledge_id IS NOT NULL"
        ).fetchone()[0]
        pledge_count = connection.execute(
            "SELECT COUNT(*) FROM farmer_pledges"
        ).fetchone()[0]
        pledges_with_multiple_logs = connection.execute(
            """
            SELECT COUNT(*)
            FROM (
                SELECT farmer_pledge_id
                FROM farm_input_logs
                WHERE farmer_pledge_id IS NOT NULL
                GROUP BY farmer_pledge_id
                HAVING COUNT(*) >= 2
            )
            """
        ).fetchone()[0]

    assert linked_log_count > pledge_count
    assert pledges_with_multiple_logs > max(1, pledge_count // 2)


def test_input_logs_include_specific_product_and_method_details(test_database_path):
    """Input logs should support future buyer-rule matching with specific product metadata."""
    with sqlite3.connect(test_database_path) as connection:
        missing_product_names = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE product_name IS NULL OR TRIM(product_name) = ''"
        ).fetchone()[0]
        missing_methods = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE application_method IS NULL OR TRIM(application_method) = ''"
        ).fetchone()[0]
        branded_logs = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE brand_name IS NOT NULL AND TRIM(brand_name) != ''"
        ).fetchone()[0]
        category_count = connection.execute(
            "SELECT COUNT(DISTINCT input_type) FROM farm_input_logs"
        ).fetchone()[0]

    assert missing_product_names == 0
    assert missing_methods == 0
    assert branded_logs > 0
    assert category_count >= 4


def test_persist_confirmed_allocation_writes_rows_and_updates_statuses(test_database_path):
    """Submitting a confirmed allocation should insert rows and refresh pledge statuses."""
    with sqlite3.connect(test_database_path) as connection:
        buyer_pledge_id, farmer_pledge_id = connection.execute(
            """
            SELECT bp.buyer_pledge_id, fp.farmer_pledge_id
            FROM buyer_pledges AS bp
            INNER JOIN farmer_pledges AS fp
                ON bp.crop_type = fp.crop_type
            LIMIT 1
            """
        ).fetchone()

        before_count = connection.execute(
            "SELECT COUNT(*) FROM pledge_allocations WHERE buyer_pledge_id = ? AND farmer_pledge_id = ?",
            (buyer_pledge_id, farmer_pledge_id),
        ).fetchone()[0]

    persist_confirmed_allocation(
        buyer_pledge_id=buyer_pledge_id,
        selected_rows=[{"farmer_pledge_id": farmer_pledge_id, "draft_quantity_kg": 1}],
    )

    with sqlite3.connect(test_database_path) as connection:
        after_count = connection.execute(
            "SELECT COUNT(*) FROM pledge_allocations WHERE buyer_pledge_id = ? AND farmer_pledge_id = ?",
            (buyer_pledge_id, farmer_pledge_id),
        ).fetchone()[0]
        buyer_status = connection.execute(
            "SELECT pledge_status FROM buyer_pledges WHERE buyer_pledge_id = ?",
            (buyer_pledge_id,),
        ).fetchone()[0]
        farmer_status = connection.execute(
            "SELECT pledge_status FROM farmer_pledges WHERE farmer_pledge_id = ?",
            (farmer_pledge_id,),
        ).fetchone()[0]

    assert after_count == before_count + 1
    assert buyer_status in {"partial", "fulfilled"}
    assert farmer_status in {"partial", "allocated"}
