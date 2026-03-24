"""Tests for simple allocation-related helper behaviour."""

from logic.database_helpers import get_farmer_pledges_for_crop


def test_get_farmer_pledges_for_crop_returns_matching_rows(test_database_path):
    """Crop filtering should return only the requested farmer pledges."""
    pledges = get_farmer_pledges_for_crop("Tomatoes")

    assert pledges
    assert all(pledge["crop_type"] == "Tomatoes" for pledge in pledges)
