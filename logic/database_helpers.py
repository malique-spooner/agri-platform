"""Database helper functions for retrieving application data."""

from __future__ import annotations

from datetime import date, timedelta
import json
import logging
import os
from pathlib import Path
import sqlite3
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_DATABASE_PATH = PROJECT_ROOT / "database" / "app_data.db"
logger = logging.getLogger(__name__)


def get_database_path() -> Path:
    """Return the configured database path, defaulting to the local demo database."""
    database_path = Path(os.environ.get("AGRI_PLATFORM_DB_PATH", DEFAULT_DATABASE_PATH))
    logger.debug("Resolved database path: %s", database_path)
    return database_path


def get_connection() -> sqlite3.Connection:
    """Create a SQLite connection configured to return rows by column name."""
    database_path = get_database_path()
    logger.debug("Opening SQLite connection to %s", database_path)
    connection = sqlite3.connect(database_path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON;")
    return connection


def rows_to_dicts(rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
    """Convert SQLite row objects to plain dictionaries."""
    return [dict(row) for row in rows]


def summarise_buyer_criteria(notes: str | None) -> str:
    """Convert buyer pledge notes JSON into a readable summary."""
    if not notes:
        return "No additional criteria recorded"

    try:
        parsed_notes = json.loads(notes)
    except json.JSONDecodeError:
        logger.warning("Could not parse buyer pledge notes JSON")
        return "No additional criteria recorded"

    if not isinstance(parsed_notes, dict):
        return "No additional criteria recorded"

    fragments: list[str] = []

    priority = parsed_notes.get("priority")
    if priority:
        fragments.append(f"Priority: {str(priority).replace('-', ' ')}")

    organic_preference = parsed_notes.get("organic_preference")
    if organic_preference is not None:
        fragments.append("Organic preference: Yes" if organic_preference else "Organic preference: No")

    delivery_window_days = parsed_notes.get("delivery_window_days")
    if delivery_window_days is not None:
        fragments.append(f"Delivery window: {delivery_window_days} days")

    return " | ".join(fragments) if fragments else "No additional criteria recorded"


def get_deadline_state(needed_by_date: str | None) -> str:
    """Classify a buyer pledge deadline for management display."""
    if not needed_by_date:
        return "unscheduled"

    try:
        deadline = date.fromisoformat(needed_by_date)
    except ValueError:
        return "unscheduled"

    today = date.today()
    if deadline < today:
        return "overdue"
    if deadline <= today.fromordinal(today.toordinal() + 14):
        return "upcoming"
    return "scheduled"


def buyer_pledge_sort_key(pledge: dict[str, Any]) -> tuple[int, str, int]:
    """Return a stable management-oriented sort key for buyer pledges."""
    status_priority = {"open": 0, "partial": 1, "fulfilled": 2}
    needed_by_date = pledge.get("needed_by_date") or "9999-12-31"
    return (
        status_priority.get(str(pledge.get("pledge_status", "")).lower(), 99),
        needed_by_date,
        int(pledge["buyer_pledge_id"]),
    )


def get_all_buyer_pledges() -> list[dict[str, Any]]:
    """Return all buyer pledges with the buyer organisation name attached."""
    logger.info("Fetching all buyer pledges")
    query = """
        SELECT
            bp.buyer_pledge_id,
            ba.organisation_name,
            bp.crop_type,
            bp.quantity_kg,
            bp.target_price_per_kg,
            bp.needed_by_date,
            bp.pledge_status,
            bp.notes,
            COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity_kg
        FROM buyer_pledges AS bp
        INNER JOIN buyer_accounts AS ba
            ON bp.buyer_account_id = ba.buyer_account_id
        LEFT JOIN pledge_allocations AS pa
            ON bp.buyer_pledge_id = pa.buyer_pledge_id
        GROUP BY
            bp.buyer_pledge_id,
            ba.organisation_name,
            bp.crop_type,
            bp.quantity_kg,
            bp.target_price_per_kg,
            bp.needed_by_date,
            bp.pledge_status,
            bp.notes
    """

    with get_connection() as connection:
        rows = connection.execute(query).fetchall()

    pledges = rows_to_dicts(rows)
    for pledge in pledges:
        allocated_quantity = float(pledge.get("allocated_quantity_kg") or 0)
        required_quantity = float(pledge.get("quantity_kg") or 0)
        pledge["criteria_summary"] = summarise_buyer_criteria(pledge.get("notes"))
        pledge["deadline_state"] = get_deadline_state(pledge.get("needed_by_date"))
        pledge["remaining_quantity_kg"] = max(required_quantity - allocated_quantity, 0)
        pledge["fulfillment_percent"] = (
            round((allocated_quantity / required_quantity) * 100, 1) if required_quantity else 0
        )

    sorted_pledges = sorted(pledges, key=buyer_pledge_sort_key)
    logger.info("Fetched %s buyer pledge record(s)", len(sorted_pledges))
    return sorted_pledges


def get_all_farms() -> list[dict[str, Any]]:
    """Return farmer accounts with summary metrics for the farm directory."""
    logger.info("Fetching all farm records")
    query = """
        SELECT
            fa.farmer_account_id,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            fa.latitude,
            fa.longitude,
            fa.email,
            fa.phone,
            fa.total_hectares,
            COUNT(DISTINCT fp.farmer_pledge_id) AS pledge_count,
            COUNT(DISTINCT fp.crop_type) AS crop_count,
            COALESCE(SUM(fp.quantity_kg), 0) AS total_supply_kg,
            GROUP_CONCAT(DISTINCT fp.crop_type) AS crop_types,
            MIN(fp.available_from_date) AS next_available_date
        FROM farmer_accounts AS fa
        LEFT JOIN farmer_pledges AS fp
            ON fa.farmer_account_id = fp.farmer_account_id
        GROUP BY
            fa.farmer_account_id,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            fa.latitude,
            fa.longitude,
            fa.email,
            fa.phone,
            fa.total_hectares
        ORDER BY fa.farm_name
    """

    with get_connection() as connection:
        rows = connection.execute(query).fetchall()

    farms = rows_to_dicts(rows)
    today = date.today()
    available_soon_cutoff = today + timedelta(days=30)

    for farm in farms:
        crop_types = farm.get("crop_types")
        farm["crop_types"] = [] if not crop_types else [crop.strip() for crop in str(crop_types).split(",") if crop.strip()]
        next_available_date = farm.get("next_available_date")
        farm["has_active_offers"] = int(farm.get("pledge_count") or 0) > 0
        if not next_available_date:
            farm["available_soon"] = False
        else:
            try:
                farm["available_soon"] = date.fromisoformat(str(next_available_date)) <= available_soon_cutoff
            except ValueError:
                farm["available_soon"] = False

    logger.info("Fetched %s farm record(s)", len(farms))
    return farms


def get_farm_by_id(farm_id: int) -> dict[str, Any] | None:
    """Return a single farm profile by its identifier."""
    logger.info("Fetching farm profile for id=%s", farm_id)
    query = """
        SELECT
            fa.farmer_account_id,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            fa.latitude,
            fa.longitude,
            fa.email,
            fa.phone,
            fa.total_hectares,
            COUNT(DISTINCT fp.farmer_pledge_id) AS pledge_count,
            COUNT(DISTINCT fp.crop_type) AS crop_count,
            COALESCE(SUM(fp.quantity_kg), 0) AS total_supply_kg,
            MIN(fp.available_from_date) AS next_available_date
        FROM farmer_accounts AS fa
        LEFT JOIN farmer_pledges AS fp
            ON fa.farmer_account_id = fp.farmer_account_id
        WHERE fa.farmer_account_id = ?
        GROUP BY
            fa.farmer_account_id,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            fa.latitude,
            fa.longitude,
            fa.email,
            fa.phone,
            fa.total_hectares
    """

    with get_connection() as connection:
        row = connection.execute(query, (farm_id,)).fetchone()

    if row:
        logger.info("Found farm profile for id=%s", farm_id)
    else:
        logger.warning("No farm profile found for id=%s", farm_id)
    return dict(row) if row else None


def get_farmer_pledges_for_farm(farm_id: int) -> list[dict[str, Any]]:
    """Return all pledges for a single farm."""
    logger.info("Fetching farmer pledges for farm id=%s", farm_id)
    query = """
        SELECT
            farmer_pledge_id,
            crop_type,
            quantity_kg,
            asking_price_per_kg,
            available_from_date,
            pledge_status,
            notes,
            created_at
        FROM farmer_pledges
        WHERE farmer_account_id = ?
        ORDER BY available_from_date, farmer_pledge_id
    """

    with get_connection() as connection:
        rows = connection.execute(query, (farm_id,)).fetchall()

    logger.info("Fetched %s farmer pledge record(s) for farm id=%s", len(rows), farm_id)
    return rows_to_dicts(rows)


def get_farmer_pledge_by_id(farm_id: int, pledge_id: int) -> dict[str, Any] | None:
    """Return a single farmer pledge belonging to a farm."""
    logger.info("Fetching farmer pledge id=%s for farm id=%s", pledge_id, farm_id)
    query = """
        SELECT
            farmer_pledge_id,
            farmer_account_id,
            crop_type,
            quantity_kg,
            asking_price_per_kg,
            available_from_date,
            pledge_status,
            notes,
            created_at
        FROM farmer_pledges
        WHERE farmer_account_id = ?
          AND farmer_pledge_id = ?
    """

    with get_connection() as connection:
        row = connection.execute(query, (farm_id, pledge_id)).fetchone()

    if row:
        logger.info("Found farmer pledge id=%s for farm id=%s", pledge_id, farm_id)
    else:
        logger.warning("No farmer pledge id=%s found for farm id=%s", pledge_id, farm_id)
    return dict(row) if row else None


def get_input_logs_for_pledge(farm_id: int, pledge_id: int) -> list[dict[str, Any]]:
    """Return input logs for a specific farmer pledge."""
    logger.info("Fetching input logs for farm id=%s and pledge id=%s", farm_id, pledge_id)
    query = """
        SELECT
            fil.input_log_id,
            fil.input_type,
            fil.product_name,
            fil.brand_name,
            fil.application_method,
            fil.quantity,
            fil.unit,
            fil.log_date,
            fil.notes,
            fp.crop_type
        FROM farm_input_logs AS fil
        INNER JOIN farmer_pledges AS fp
            ON fil.farmer_pledge_id = fp.farmer_pledge_id
        WHERE fil.farmer_account_id = ?
          AND fil.farmer_pledge_id = ?
        ORDER BY fil.log_date DESC, fil.input_log_id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(query, (farm_id, pledge_id)).fetchall()

    logger.info(
        "Fetched %s input log record(s) for farm id=%s and pledge id=%s",
        len(rows),
        farm_id,
        pledge_id,
    )
    return rows_to_dicts(rows)


def get_farmer_pledges_for_crop(crop_type: str) -> list[dict[str, Any]]:
    """Return farmer pledges that match a requested crop type."""
    logger.info("Fetching farmer pledges for crop_type=%s", crop_type)
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

    logger.info(
        "Fetched %s farmer pledge record(s) for crop_type=%s",
        len(rows),
        crop_type,
    )
    return rows_to_dicts(rows)
