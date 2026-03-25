"""Tests for the server-rendered allocation builder page."""

from __future__ import annotations

import app as app_module
from logic.database_helpers import get_all_buyer_pledges


def test_build_allocation_page_returns_success(client):
    """A valid buyer pledge should open the allocation builder page."""
    response = client.get("/buyer-pledges/1/allocation")

    assert response.status_code == 200
    assert b"Build Allocation" in response.data
    assert b"Staged For Submission" in response.data
    assert b"Submitted:" in response.data
    assert b"Staged:" in response.data
    assert b"Remaining after submit:" in response.data
    assert b"Submit allocation" in response.data
    assert b"Export buyer summary" in response.data
    assert b"Export farm summary" in response.data
    assert b"Matching Crop Offers" in response.data
    assert b"Required" in response.data
    assert b"Blocked" in response.data
    assert b'Hide ineligible crop offers' in response.data


def test_build_allocation_page_filters_farms_to_matching_crop(client, monkeypatch):
    """The allocation builder should only show eligible farms for the buyer crop."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 200,
            "remaining_quantity_kg": 1000,
            "needed_by_date": "2026-08-01",
            "pledge_status": "open",
            "display_status": "Not started",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda crop_type: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
                "crop_type": crop_type,
                "criteria_status": "eligible",
                "criteria_message": "Matches current buyer rules",
                "recent_inputs": ["Fertiliser / Organic compost"],
                "input_logs": [],
                "missing_required": [],
                "blocked_matches": [],
                "is_selectable": True,
            }
        ],
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {11: []})

    response = client.get("/buyer-pledges/1/allocation?hide_ineligible=0")

    assert response.status_code == 200
    assert b"Riverbend Farm" in response.data
    assert b"Beans" in response.data
    assert b"Required" in response.data
    assert b"Blocked" in response.data
    assert b"Hide ineligible crop offers" in response.data
    assert b"Crop history" in response.data


def test_build_allocation_page_adds_suggested_quantity_to_draft(client, monkeypatch):
    """Adding a crop offer should use the suggested automatic quantity."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 200,
            "remaining_quantity_kg": 1000,
            "needed_by_date": "2026-08-01",
            "pledge_status": "partial",
            "display_status": "In progress",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
                "criteria_status": "eligible",
                "criteria_message": "Matches current buyer rules",
                "recent_inputs": ["Fertiliser / Organic compost"],
                "input_logs": [],
                "missing_required": [],
                "blocked_matches": [],
                "is_selectable": True,
            },
            {
                "farmer_pledge_id": 12,
                "farmer_account_id": 4,
                "farm_name": "Sunrise Fields",
                "farmer_name": "Amina Njoroge",
                "county": "Kiambu",
                "region": "Kenya",
                "available_quantity_kg": 500,
                "available_from_date": "2026-06-03",
                "asking_price_per_kg": 1.9,
                "criteria_status": "eligible",
                "criteria_message": "Matches current buyer rules",
                "recent_inputs": ["Irrigation / Drip irrigation cycle"],
                "input_logs": [],
                "missing_required": [],
                "blocked_matches": [],
                "is_selectable": True,
            },
        ],
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {11: [], 12: []})

    response = client.post(
        "/buyer-pledges/1/allocation",
        data={
            "action": "add",
            "selected_offer_id": "11",
            "selected_quantity_kg": "275",
        },
    )

    assert response.status_code == 200
    assert b"Submitted: 200 kg" in response.data
    assert b"Staged: 275.0 kg" in response.data
    assert b"Remaining after submit: 725.0 kg" in response.data
    assert b"Riverbend Farm" in response.data
    assert b"Staged for submission." in response.data


def test_build_allocation_page_renders_validation_error_for_excess_total(client, monkeypatch):
    """The builder should stop adding when no remaining buyer demand is left."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 400,
            "remaining_quantity_kg": 300,
            "needed_by_date": "2026-08-01",
            "pledge_status": "partial",
            "display_status": "In progress",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
                "criteria_status": "eligible",
                "criteria_message": "Matches current buyer rules",
                "recent_inputs": [],
                "input_logs": [],
                "missing_required": [],
                "blocked_matches": [],
                "is_selectable": True,
            }
        ],
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {11: []})

    response = client.post(
        "/buyer-pledges/1/allocation",
        data={"action": "add", "selected_offer_id": "11"},
    )

    assert response.status_code == 200
    assert b"300.0 kg" in response.data

    second_response = client.post(
        "/buyer-pledges/1/allocation",
        data={"action": "add", "selected_offer_id": "11"},
    )

    assert second_response.status_code == 200
    assert b"No remaining demand is left to allocate" in second_response.data


def test_build_allocation_page_shows_blocked_crop_offer_as_not_selectable(client, monkeypatch):
    """Blocked crop offers should be shown but not offered for selection."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 0,
            "remaining_quantity_kg": 1200,
            "needed_by_date": "2026-08-01",
            "pledge_status": "open",
            "display_status": "Not started",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": [{"input_type": "Pesticide", "product_name": "Pyrethrin spray"}]},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
            }
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_input_logs_for_pledge_ids",
        lambda _: {
            11: [
                {
                    "input_type": "Pesticide",
                    "product_name": "Pyrethrin spray",
                    "brand_name": None,
                }
            ]
        },
    )

    response = client.get("/buyer-pledges/1/allocation?hide_ineligible=0")

    assert response.status_code == 200
    assert b"Blocked" in response.data
    assert b"disabled" in response.data


def test_build_allocation_buyer_export_returns_pdf(client):
    """The buyer export action should return a downloadable PDF."""
    fulfilled_pledge_id = next(
        int(pledge["buyer_pledge_id"])
        for pledge in get_all_buyer_pledges()
        if pledge["pledge_status"] == "fulfilled"
    )
    response = client.post(
        f"/buyer-pledges/{fulfilled_pledge_id}/allocation",
        data={"action": "export_buyer_summary"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert f"buyer-pledge-{fulfilled_pledge_id}-batch-summary.pdf" in response.headers["Content-Disposition"]


def test_build_allocation_farmer_export_returns_pdf(client):
    """The farmer export action should return a downloadable PDF."""
    fulfilled_pledge_id = next(
        int(pledge["buyer_pledge_id"])
        for pledge in get_all_buyer_pledges()
        if pledge["pledge_status"] == "fulfilled"
    )
    response = client.post(
        f"/buyer-pledges/{fulfilled_pledge_id}/allocation",
        data={"action": "export_farm_summary"},
    )

    assert response.status_code == 200
    assert response.mimetype == "application/pdf"
    assert response.data.startswith(b"%PDF")
    assert f"buyer-pledge-{fulfilled_pledge_id}-farmer-summary.pdf" in response.headers["Content-Disposition"]


def test_build_allocation_export_is_blocked_until_batch_is_complete(client, monkeypatch):
    """Incomplete buyer pledges should not be exportable."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 200,
            "remaining_quantity_kg": 1000,
            "needed_by_date": "2026-08-01",
            "pledge_status": "partial",
            "display_status": "In progress",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(app_module, "get_farmer_pledges_for_crop", lambda _: [])
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {})

    response = client.post("/buyer-pledges/1/allocation", data={"action": "export_buyer_summary"})

    assert response.status_code == 200
    assert response.mimetype == "text/html"
    assert b"Complete the batch before exporting reports." in response.data


def test_build_allocation_page_can_hide_ineligible_offers(client, monkeypatch):
    """The hide toggle should remove ineligible crop offers from the visible list."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 0,
            "remaining_quantity_kg": 1200,
            "needed_by_date": "2026-08-01",
            "pledge_status": "open",
            "display_status": "Not started",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Eligible Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
            },
            {
                "farmer_pledge_id": 12,
                "farmer_account_id": 4,
                "farm_name": "Blocked Farm",
                "farmer_name": "Amina Njoroge",
                "county": "Kiambu",
                "region": "Kenya",
                "available_quantity_kg": 500,
                "available_from_date": "2026-06-03",
                "asking_price_per_kg": 1.9,
            },
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_input_logs_for_pledge_ids",
        lambda _: {
            11: [],
            12: [{"input_type": "Pesticide", "product_name": "Pyrethrin spray", "brand_name": None}],
        },
    )

    buyer_with_block = {
        "buyer_pledge_id": 1,
        "organisation_name": "Buyer One",
        "crop_type": "Beans",
        "quantity_kg": 1200,
        "allocated_quantity_kg": 0,
        "remaining_quantity_kg": 1200,
        "needed_by_date": "2026-08-01",
        "pledge_status": "open",
        "display_status": "Not started",
        "criteria_summary": "Priority: standard",
        "criteria": {"required_inputs": [], "blocked_inputs": [{"input_type": "Pesticide", "product_name": "Pyrethrin spray"}]},
    }
    monkeypatch.setattr(app_module, "get_buyer_pledge_by_id", lambda _: buyer_with_block)

    response = client.get("/buyer-pledges/1/allocation?hide_ineligible=1")

    assert response.status_code == 200
    assert b"Eligible Farm" in response.data
    assert b"Blocked Farm" not in response.data


def test_build_allocation_page_hides_blocked_offers_when_checkbox_submits_two_values(client, monkeypatch):
    """The checked hide toggle should still work when the form submits both 0 and 1 values."""
    buyer_with_block = {
        "buyer_pledge_id": 1,
        "organisation_name": "Buyer One",
        "crop_type": "Beans",
        "quantity_kg": 1200,
        "allocated_quantity_kg": 0,
        "remaining_quantity_kg": 1200,
        "needed_by_date": "2026-08-01",
        "pledge_status": "open",
        "display_status": "Not started",
        "criteria_summary": "Priority: standard",
        "criteria": {"required_inputs": [], "blocked_inputs": [{"input_type": "Pesticide", "product_name": "Pyrethrin spray"}]},
    }
    monkeypatch.setattr(app_module, "get_buyer_pledge_by_id", lambda _: buyer_with_block)
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Eligible Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
            },
            {
                "farmer_pledge_id": 12,
                "farmer_account_id": 4,
                "farm_name": "Blocked Farm",
                "farmer_name": "Amina Njoroge",
                "county": "Kiambu",
                "region": "Kenya",
                "available_quantity_kg": 500,
                "available_from_date": "2026-06-03",
                "asking_price_per_kg": 1.9,
            },
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_input_logs_for_pledge_ids",
        lambda _: {
            11: [],
            12: [{"input_type": "Pesticide", "product_name": "Pyrethrin spray", "brand_name": None}],
        },
    )

    response = client.get("/buyer-pledges/1/allocation?hide_ineligible=0&hide_ineligible=1")

    assert response.status_code == 200
    assert b"Eligible Farm" in response.data
    assert b"Blocked Farm" not in response.data


def test_build_allocation_page_hide_toggle_keeps_review_offers_visible(client, monkeypatch):
    """The hide toggle should remove blocked offers but keep review-needed offers visible."""
    buyer_with_rules = {
        "buyer_pledge_id": 1,
        "organisation_name": "Buyer One",
        "crop_type": "Beans",
        "quantity_kg": 1200,
        "allocated_quantity_kg": 0,
        "remaining_quantity_kg": 1200,
        "needed_by_date": "2026-08-01",
        "pledge_status": "open",
        "display_status": "Not started",
        "criteria_summary": "Priority: standard",
        "criteria": {
            "required_inputs": [{"input_type": "Irrigation", "product_name": "Drip irrigation cycle"}],
            "blocked_inputs": [{"input_type": "Pesticide", "product_name": "Pyrethrin spray"}],
        },
    }
    monkeypatch.setattr(app_module, "get_buyer_pledge_by_id", lambda _: buyer_with_rules)
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Review Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
            },
            {
                "farmer_pledge_id": 12,
                "farmer_account_id": 4,
                "farm_name": "Blocked Farm",
                "farmer_name": "Amina Njoroge",
                "county": "Kiambu",
                "region": "Kenya",
                "available_quantity_kg": 500,
                "available_from_date": "2026-06-03",
                "asking_price_per_kg": 1.9,
            },
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_input_logs_for_pledge_ids",
        lambda _: {
            11: [],
            12: [{"input_type": "Pesticide", "product_name": "Pyrethrin spray", "brand_name": None}],
        },
    )

    response = client.get("/buyer-pledges/1/allocation?hide_ineligible=1")

    assert response.status_code == 200
    assert b"Review Farm" in response.data
    assert b"Blocked Farm" not in response.data


def test_build_allocation_page_submit_writes_allocations_and_refreshes_state(client, monkeypatch):
    """Submitting a staged batch should persist rows and refresh remaining demand."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 200,
            "remaining_quantity_kg": 1000,
            "needed_by_date": "2026-08-01",
            "pledge_status": "partial",
            "display_status": "In progress",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [
            {
                "farmer_pledge_id": 11,
                "farmer_account_id": 3,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Nakuru",
                "region": "Kenya",
                "available_quantity_kg": 400,
                "available_from_date": "2026-06-01",
                "asking_price_per_kg": 1.7,
            }
        ],
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {11: []})

    client.post("/buyer-pledges/1/allocation", data={"action": "add", "selected_offer_id": "11"})

    persisted = {}

    def fake_persist_confirmed_allocation(buyer_pledge_id, selected_rows):
        persisted["buyer_pledge_id"] = buyer_pledge_id
        persisted["selected_rows"] = selected_rows

    monkeypatch.setattr(app_module, "persist_confirmed_allocation", fake_persist_confirmed_allocation)
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 600,
            "remaining_quantity_kg": 600,
            "needed_by_date": "2026-08-01",
            "pledge_status": "partial",
            "display_status": "In progress",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )

    submit_response = client.post("/buyer-pledges/1/allocation", data={"action": "submit"}, follow_redirects=True)

    assert submit_response.status_code == 200
    assert persisted["buyer_pledge_id"] == 1
    assert len(persisted["selected_rows"]) == 1
    assert b"Allocation submitted." in submit_response.data
    assert b"Remaining Demand" in submit_response.data
    assert b"600 kg" in submit_response.data
    assert b"No staged offers." in submit_response.data


def test_build_allocation_page_export_button_returns_pdf_with_mocked_pledge(client, monkeypatch):
    """The buyer export should still render a PDF when the page context is monkeypatched."""
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda _: {
            "buyer_pledge_id": 1,
            "organisation_name": "Buyer One",
            "crop_type": "Beans",
            "quantity_kg": 1200,
            "allocated_quantity_kg": 1200,
            "remaining_quantity_kg": 0,
            "needed_by_date": "2026-08-01",
            "pledge_status": "fulfilled",
            "display_status": "Completed",
            "criteria_summary": "Priority: standard",
            "criteria": {"required_inputs": [], "blocked_inputs": []},
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledges_for_crop",
        lambda _: [],
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge_ids", lambda _: {})

    export_response = client.post("/buyer-pledges/1/allocation", data={"action": "export_buyer_summary"})

    assert export_response.status_code == 200
    assert export_response.mimetype == "application/pdf"
    assert export_response.data.startswith(b"%PDF")


def test_build_allocation_page_returns_404_for_unknown_pledge(client):
    """An unknown buyer pledge should return 404."""
    response = client.get("/buyer-pledges/999999/allocation")

    assert response.status_code == 404
