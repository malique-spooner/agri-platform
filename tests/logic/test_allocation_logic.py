"""Tests for allocation helper behaviour."""

import sqlite3

from logic.allocation_logic import build_draft_allocation, suggested_allocation_quantity
from logic.database_helpers import get_farmer_pledges_for_crop


def test_get_farmer_pledges_for_crop_returns_matching_rows(test_database_path):
    """Crop filtering should return only the requested farmer pledges."""
    with sqlite3.connect(test_database_path) as connection:
        crop_type = connection.execute(
            """
            SELECT crop_type
            FROM farmer_pledges
            GROUP BY crop_type
            ORDER BY COUNT(*) DESC, crop_type
            LIMIT 1
            """
        ).fetchone()[0]

    pledges = get_farmer_pledges_for_crop(crop_type)

    assert pledges
    assert all(pledge["crop_type"] == crop_type for pledge in pledges)
    assert all(pledge["available_quantity_kg"] > 0 for pledge in pledges)


def test_build_draft_allocation_summarises_valid_selection():
    """Draft allocation should total selected farm contributions."""
    result = build_draft_allocation(
        buyer_pledge={"remaining_quantity_kg": 900},
        eligible_pledges=[
            {"farmer_pledge_id": 1, "farm_name": "Alpha Farm", "available_quantity_kg": 500},
            {"farmer_pledge_id": 2, "farm_name": "Beta Farm", "available_quantity_kg": 600},
        ],
        submitted_quantities={1: "300", 2: "200"},
    )

    assert result["total_allocated_kg"] == 500
    assert result["remaining_after_kg"] == 400
    assert not result["errors"]


def test_build_draft_allocation_rejects_quantity_above_available_supply():
    """Draft allocation should reject selections that exceed farm availability."""
    result = build_draft_allocation(
        buyer_pledge={"remaining_quantity_kg": 900},
        eligible_pledges=[
            {"farmer_pledge_id": 1, "farm_name": "Alpha Farm", "available_quantity_kg": 250},
        ],
        submitted_quantities={1: "300"},
    )

    assert result["errors"]
    assert "Alpha Farm can only contribute up to 250 kg." in result["errors"][0]


def test_build_draft_allocation_rejects_non_selectable_pledges():
    """Draft allocation should reject offers that fail buyer criteria."""
    result = build_draft_allocation(
        buyer_pledge={"remaining_quantity_kg": 900},
        eligible_pledges=[
            {
                "farmer_pledge_id": 1,
                "farm_name": "Gamma Farm",
                "available_quantity_kg": 250,
                "is_selectable": False,
            },
        ],
        submitted_quantities={1: "200"},
    )

    assert result["errors"] == ["Gamma Farm does not currently satisfy the buyer criteria."]
    assert result["selected_rows"] == []


def test_suggested_allocation_quantity_caps_at_remaining_demand():
    """Suggested quantities should never exceed the buyer's remaining demand."""
    assert suggested_allocation_quantity(120, 400) == 120
    assert suggested_allocation_quantity(0, 400) == 0.0
