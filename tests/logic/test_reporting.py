"""Tests for PDF reporting outputs."""

from __future__ import annotations

from logic.database_helpers import (
    get_all_buyer_pledges,
    get_farmer_pledges_for_crop,
    persist_confirmed_allocation,
)
from logic.reporting import build_buyer_summary_pdf, build_farmer_summary_pdf, fetch_batch_report_context


def test_build_buyer_summary_pdf_returns_pdf_bytes(test_database_path):
    """Buyer batch reports should render into valid PDF bytes."""
    buyer_pledge_id = int(get_all_buyer_pledges()[0]["buyer_pledge_id"])

    pdf_bytes = build_buyer_summary_pdf(buyer_pledge_id)

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1500


def test_build_farmer_summary_pdf_handles_confirmed_contributions(test_database_path):
    """Farmer participation reports should render after allocations have been persisted."""
    buyer_pledge = next(
        pledge
        for pledge in get_all_buyer_pledges()
        if get_farmer_pledges_for_crop(str(pledge["crop_type"]))
    )
    eligible_pledges = get_farmer_pledges_for_crop(str(buyer_pledge["crop_type"]))
    selected = eligible_pledges[0]
    selected_quantity = min(
        float(buyer_pledge["remaining_quantity_kg"]),
        float(selected["available_quantity_kg"]),
    )
    persist_confirmed_allocation(
        buyer_pledge_id=int(buyer_pledge["buyer_pledge_id"]),
        selected_rows=[{**selected, "draft_quantity_kg": selected_quantity}],
    )

    context = fetch_batch_report_context(int(buyer_pledge["buyer_pledge_id"]))
    pdf_bytes = build_farmer_summary_pdf(int(buyer_pledge["buyer_pledge_id"]))

    assert context["farms"]
    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1800


def test_build_buyer_summary_pdf_handles_open_batches_without_allocations(test_database_path):
    """Buyer reports should still render when a pledge exists but has no confirmed allocations yet."""
    buyer_pledge = next(
        pledge
        for pledge in get_all_buyer_pledges()
        if pledge["pledge_status"] == "open"
    )

    pdf_bytes = build_buyer_summary_pdf(int(buyer_pledge["buyer_pledge_id"]))

    assert pdf_bytes.startswith(b"%PDF")
    assert len(pdf_bytes) > 1200
