"""Focused tests for database helper shaping and query behavior."""

from __future__ import annotations

import sqlite3

from logic.database_helpers import (
    get_all_buyer_pledges,
    get_deadline_state,
    get_farmer_pledges_for_crop,
    get_input_logs_for_pledge_ids,
    parse_buyer_criteria,
    summarise_buyer_criteria,
)


def test_summarise_buyer_criteria_returns_readable_text():
    """Structured buyer notes should be condensed into a human-readable summary."""
    summary = summarise_buyer_criteria(
        """
        {
            "priority": "bulk-distribution",
            "organic_preference": true,
            "delivery_window_days": 5,
            "required_inputs": [{"input_type": "Fertiliser", "product_name": "Organic compost"}],
            "blocked_inputs": [{"input_type": "Pesticide", "product_name": "Pyrethrin spray"}]
        }
        """
    )

    assert "Priority: bulk distribution" in summary
    assert "Organic preference: Yes" in summary
    assert "Delivery window: 5 days" in summary
    assert "Required checks: 1" in summary
    assert "Blocked checks: 1" in summary


def test_parse_buyer_criteria_falls_back_for_invalid_json():
    """Invalid notes JSON should not break helper consumers."""
    criteria = parse_buyer_criteria("{not valid json}")

    assert criteria == {
        "priority": None,
        "organic_preference": None,
        "delivery_window_days": None,
        "required_inputs": [],
        "blocked_inputs": [],
    }


def test_get_deadline_state_classifies_missing_dates_as_unscheduled():
    """Missing or bad deadlines should fall back to the unscheduled state."""
    assert get_deadline_state(None) == "unscheduled"
    assert get_deadline_state("not-a-date") == "unscheduled"


def test_get_all_buyer_pledges_includes_display_and_progress_fields(test_database_path):
    """Buyer pledge rows should expose the derived fields used by the homepage."""
    pledges = get_all_buyer_pledges()

    assert pledges
    first = pledges[0]
    assert first["display_status"] in {"Not started", "In progress", "Completed"}
    assert "criteria_summary" in first
    assert "criteria" in first
    assert "remaining_quantity_kg" in first
    assert "fulfillment_percent" in first
    assert first["remaining_quantity_kg"] >= 0


def test_get_farmer_pledges_for_crop_only_returns_rows_with_remaining_supply(test_database_path):
    """Crop queries should exclude fully allocated farmer pledges."""
    crop_type = get_all_buyer_pledges()[0]["crop_type"]
    pledges = get_farmer_pledges_for_crop(crop_type)

    assert pledges
    assert all(float(pledge["available_quantity_kg"]) > 0 for pledge in pledges)
    assert all(pledge["crop_type"] == crop_type for pledge in pledges)


def test_get_input_logs_for_pledge_ids_returns_logs_keyed_by_requested_ids(test_database_path):
    """Bulk input-log fetches should preserve the requested pledge-id shape."""
    with sqlite3.connect(test_database_path) as connection:
        pledge_ids = [
            row[0]
            for row in connection.execute(
                """
                SELECT farmer_pledge_id
                FROM farm_input_logs
                WHERE farmer_pledge_id IS NOT NULL
                GROUP BY farmer_pledge_id
                ORDER BY farmer_pledge_id
                LIMIT 2
                """
            ).fetchall()
        ]

    logs_by_pledge_id = get_input_logs_for_pledge_ids(pledge_ids)

    assert set(logs_by_pledge_id) == set(pledge_ids)
    assert all(logs_by_pledge_id[pledge_id] for pledge_id in pledge_ids)
    for pledge_id, logs in logs_by_pledge_id.items():
        assert all(int(log["farmer_pledge_id"]) == pledge_id for log in logs)
