"""Database helper functions for retrieving application data."""

from __future__ import annotations

from datetime import date, datetime, timedelta
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

    required_inputs = parsed_notes.get("required_inputs")
    if isinstance(required_inputs, list) and required_inputs:
        fragments.append(f"Required checks: {len(required_inputs)}")

    blocked_inputs = parsed_notes.get("blocked_inputs")
    if isinstance(blocked_inputs, list) and blocked_inputs:
        fragments.append(f"Blocked checks: {len(blocked_inputs)}")

    return " | ".join(fragments) if fragments else "No additional criteria recorded"


def parse_buyer_criteria(notes: str | None) -> dict[str, Any]:
    """Parse buyer notes JSON into a structured criteria payload."""
    default_payload = {
        "priority": None,
        "organic_preference": None,
        "delivery_window_days": None,
        "required_inputs": [],
        "blocked_inputs": [],
    }
    if not notes:
        return default_payload

    try:
        parsed_notes = json.loads(notes)
    except json.JSONDecodeError:
        logger.warning("Could not parse buyer pledge notes JSON for structured criteria")
        return default_payload

    if not isinstance(parsed_notes, dict):
        return default_payload

    required_inputs = parsed_notes.get("required_inputs")
    blocked_inputs = parsed_notes.get("blocked_inputs")
    return {
        "priority": parsed_notes.get("priority"),
        "organic_preference": parsed_notes.get("organic_preference"),
        "delivery_window_days": parsed_notes.get("delivery_window_days"),
        "required_inputs": required_inputs if isinstance(required_inputs, list) else [],
        "blocked_inputs": blocked_inputs if isinstance(blocked_inputs, list) else [],
    }


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
        -float(pledge.get("remaining_quantity_kg") or 0),
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
        raw_status = str(pledge.get("pledge_status", "")).lower()
        pledge["criteria_summary"] = summarise_buyer_criteria(pledge.get("notes"))
        pledge["criteria"] = parse_buyer_criteria(pledge.get("notes"))
        pledge["deadline_state"] = get_deadline_state(pledge.get("needed_by_date"))
        pledge["remaining_quantity_kg"] = max(required_quantity - allocated_quantity, 0)
        pledge["fulfillment_percent"] = (
            round((allocated_quantity / required_quantity) * 100, 1) if required_quantity else 0
        )
        pledge["display_status"] = {
            "open": "Not started",
            "partial": "In progress",
            "fulfilled": "Completed",
        }.get(raw_status, "Unknown")

    sorted_pledges = sorted(pledges, key=buyer_pledge_sort_key)
    logger.info("Fetched %s buyer pledge record(s)", len(sorted_pledges))
    return sorted_pledges


def get_buyer_pledge_by_id(buyer_pledge_id: int) -> dict[str, Any] | None:
    """Return a single buyer pledge with derived management fields."""
    logger.info("Fetching buyer pledge id=%s", buyer_pledge_id)
    pledges = get_all_buyer_pledges()
    pledge = next(
        (pledge for pledge in pledges if int(pledge.get("buyer_pledge_id", 0)) == buyer_pledge_id),
        None,
    )
    if pledge is None:
        logger.warning("No buyer pledge found for id=%s", buyer_pledge_id)
    else:
        logger.info("Found buyer pledge id=%s with status=%s", buyer_pledge_id, pledge.get("pledge_status"))
    return pledge


def persist_confirmed_allocation(
    buyer_pledge_id: int,
    selected_rows: list[dict[str, Any]],
) -> None:
    """Persist a confirmed allocation batch and refresh pledge statuses."""
    logger.info(
        "Persisting confirmed allocation for buyer pledge id=%s with %s staged row(s)",
        buyer_pledge_id,
        len(selected_rows),
    )
    created_at = datetime.now().replace(microsecond=0).isoformat(sep=" ")
    farmer_pledge_ids = [int(row["farmer_pledge_id"]) for row in selected_rows]

    with get_connection() as connection:
        for row in selected_rows:
            connection.execute(
                """
                INSERT INTO pledge_allocations (
                    buyer_pledge_id,
                    farmer_pledge_id,
                    allocated_quantity_kg,
                    allocation_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    buyer_pledge_id,
                    int(row["farmer_pledge_id"]),
                    float(row["draft_quantity_kg"]),
                    "confirmed",
                    created_at,
                ),
            )

        buyer_allocation_total = connection.execute(
            """
            SELECT COALESCE(SUM(allocated_quantity_kg), 0)
            FROM pledge_allocations
            WHERE buyer_pledge_id = ?
            """,
            (buyer_pledge_id,),
        ).fetchone()[0]
        buyer_quantity = connection.execute(
            "SELECT quantity_kg FROM buyer_pledges WHERE buyer_pledge_id = ?",
            (buyer_pledge_id,),
        ).fetchone()[0]
        buyer_status = (
            "open"
            if buyer_allocation_total == 0
            else "fulfilled"
            if float(buyer_allocation_total) >= float(buyer_quantity)
            else "partial"
        )
        connection.execute(
            "UPDATE buyer_pledges SET pledge_status = ? WHERE buyer_pledge_id = ?",
            (buyer_status, buyer_pledge_id),
        )
        logger.info(
            "Buyer pledge id=%s refreshed to status=%s after confirmed total=%.2f",
            buyer_pledge_id,
            buyer_status,
            float(buyer_allocation_total),
        )

        for farmer_pledge_id in farmer_pledge_ids:
            farmer_allocation_total = connection.execute(
                """
                SELECT COALESCE(SUM(allocated_quantity_kg), 0)
                FROM pledge_allocations
                WHERE farmer_pledge_id = ?
                """,
                (farmer_pledge_id,),
            ).fetchone()[0]
            farmer_quantity = connection.execute(
                "SELECT quantity_kg FROM farmer_pledges WHERE farmer_pledge_id = ?",
                (farmer_pledge_id,),
            ).fetchone()[0]
            farmer_status = (
                "available"
                if farmer_allocation_total == 0
                else "allocated"
                if float(farmer_allocation_total) >= float(farmer_quantity)
                else "partial"
            )
            connection.execute(
                "UPDATE farmer_pledges SET pledge_status = ? WHERE farmer_pledge_id = ?",
                (farmer_status, farmer_pledge_id),
            )
            logger.info(
                "Farmer pledge id=%s refreshed to status=%s after confirmed total=%.2f",
                farmer_pledge_id,
                farmer_status,
                float(farmer_allocation_total),
            )

        connection.commit()
    logger.info(
        "Confirmed allocation persisted for buyer pledge id=%s with %s row(s)",
        buyer_pledge_id,
        len(selected_rows),
    )


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


def get_input_logs_for_pledge_ids(pledge_ids: list[int]) -> dict[int, list[dict[str, Any]]]:
    """Return input logs for multiple farmer pledges keyed by pledge id."""
    if not pledge_ids:
        logger.info("Skipping bulk input-log fetch because no pledge ids were provided")
        return {}

    placeholders = ", ".join("?" for _ in pledge_ids)
    query = f"""
        SELECT
            input_log_id,
            farmer_pledge_id,
            input_type,
            product_name,
            brand_name,
            application_method,
            quantity,
            unit,
            log_date,
            notes
        FROM farm_input_logs
        WHERE farmer_pledge_id IN ({placeholders})
        ORDER BY log_date DESC, input_log_id DESC
    """

    with get_connection() as connection:
        rows = connection.execute(query, pledge_ids).fetchall()

    logs_by_pledge_id: dict[int, list[dict[str, Any]]] = {pledge_id: [] for pledge_id in pledge_ids}
    for row in rows_to_dicts(rows):
        logs_by_pledge_id.setdefault(int(row["farmer_pledge_id"]), []).append(row)
    logger.info(
        "Fetched %s input log record(s) across %s pledge id(s)",
        len(rows),
        len(pledge_ids),
    )
    return logs_by_pledge_id


def get_farmer_pledges_for_crop(crop_type: str) -> list[dict[str, Any]]:
    """Return farmer pledges that match a requested crop type with remaining supply."""
    logger.info("Fetching farmer pledges for crop_type=%s", crop_type)
    query = """
        SELECT
            fp.farmer_pledge_id,
            fp.farmer_account_id,
            fp.crop_type,
            fp.quantity_kg,
            fp.asking_price_per_kg,
            fp.available_from_date,
            fp.pledge_status,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity_kg
        FROM farmer_pledges AS fp
        INNER JOIN farmer_accounts AS fa
            ON fp.farmer_account_id = fa.farmer_account_id
        LEFT JOIN pledge_allocations AS pa
            ON fp.farmer_pledge_id = pa.farmer_pledge_id
        WHERE fp.crop_type = ?
        GROUP BY
            fp.farmer_pledge_id,
            fp.farmer_account_id,
            fp.crop_type,
            fp.quantity_kg,
            fp.asking_price_per_kg,
            fp.available_from_date,
            fp.pledge_status,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region
        ORDER BY fp.available_from_date, fp.farmer_pledge_id
    """

    with get_connection() as connection:
        rows = connection.execute(query, (crop_type,)).fetchall()

    pledges = rows_to_dicts(rows)
    eligible_pledges: list[dict[str, Any]] = []
    for pledge in pledges:
        available_quantity_kg = max(
            float(pledge.get("quantity_kg") or 0) - float(pledge.get("allocated_quantity_kg") or 0),
            0,
        )
        pledge["available_quantity_kg"] = available_quantity_kg
        if available_quantity_kg > 0:
            eligible_pledges.append(pledge)

    logger.info(
        "Fetched %s farmer pledge record(s) for crop_type=%s",
        len(eligible_pledges),
        crop_type,
    )
    return eligible_pledges
