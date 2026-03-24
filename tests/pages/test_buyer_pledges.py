"""Tests for the buyer pledges homepage."""

from __future__ import annotations

import app as app_module


def make_pledge(**overrides):
    """Return a queue-ready buyer pledge fixture."""
    pledge = {
        "buyer_pledge_id": 1,
        "organisation_name": "Test Buyer",
        "crop_type": "Beans",
        "quantity_kg": 1500,
        "allocated_quantity_kg": 0,
        "remaining_quantity_kg": 1500,
        "target_price_per_kg": 1.8,
        "needed_by_date": "2026-08-01",
        "pledge_status": "open",
        "display_status": "Not started",
        "criteria_summary": "Priority: standard | Organic preference: No | Delivery window: 7 days",
        "deadline_state": "scheduled",
        "fulfillment_percent": 0,
    }
    pledge.update(overrides)
    return pledge


def test_buyer_pledges_page_returns_success(client):
    """The buyer pledges page should return HTTP 200."""
    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"Buyer Pledges" in response.data
    assert b"Selected Pledge" in response.data
    assert b"Review eligible farms" in response.data
    assert b"/allocation" in response.data
    assert b'data-select-url="' in response.data


def test_buyer_pledges_page_renders_new_status_labels_not_old_section_titles(client):
    """The homepage should use presentation labels rather than the old grouped section wording."""
    response = client.get("/buyer-pledges")

    assert b"Not started" in response.data
    assert b"In progress" in response.data
    assert b"Completed" in response.data
    assert b"Open Demand" not in response.data
    assert b"Partially Fulfilled" not in response.data


def test_buyer_pledges_page_orders_completed_after_not_started_and_in_progress(client, monkeypatch):
    """Priority ordering should place active work before completed demand."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(
                buyer_pledge_id=3,
                organisation_name="Completed Buyer",
                pledge_status="fulfilled",
                display_status="Completed",
                allocated_quantity_kg=1500,
                remaining_quantity_kg=0,
                fulfillment_percent=100,
            ),
            make_pledge(
                buyer_pledge_id=2,
                organisation_name="Started Buyer",
                pledge_status="partial",
                display_status="In progress",
                allocated_quantity_kg=600,
                remaining_quantity_kg=900,
                fulfillment_percent=40,
            ),
            make_pledge(
                buyer_pledge_id=1,
                organisation_name="Not Started Buyer",
                pledge_status="open",
                display_status="Not started",
            ),
        ],
    )

    response_text = client.get("/buyer-pledges").get_data(as_text=True)

    not_started_position = response_text.find("Not Started Buyer")
    started_position = response_text.find("Started Buyer")
    completed_position = response_text.find("Completed Buyer")

    assert not_started_position != -1
    assert started_position != -1
    assert completed_position != -1
    assert not_started_position < completed_position
    assert started_position < completed_position


def test_buyer_pledges_page_uses_selected_query_param_for_detail_panel(client, monkeypatch):
    """Selecting a row by query parameter should populate the matching detail panel."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(buyer_pledge_id=1, organisation_name="First Buyer"),
            make_pledge(
                buyer_pledge_id=2,
                organisation_name="Second Buyer",
                crop_type="Tomatoes",
                pledge_status="partial",
                display_status="In progress",
                allocated_quantity_kg=500,
                remaining_quantity_kg=1000,
                fulfillment_percent=33.3,
            ),
        ],
    )

    response_text = client.get("/buyer-pledges?selected=2").get_data(as_text=True)

    assert "Second Buyer" in response_text
    assert "Tomatoes" in response_text
    assert "33.3% fulfilled" in response_text


def test_buyer_pledges_page_uses_fallbacks_for_missing_price_and_deadline(client, monkeypatch):
    """Missing target price and deadline should render fallback text."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(
                target_price_per_kg=None,
                needed_by_date=None,
                criteria_summary="No additional criteria recorded",
            )
        ],
    )

    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"TBC" in response.data
    assert b"No deadline set" in response.data
    assert b"No additional criteria recorded" in response.data


def test_buyer_pledges_page_renders_progress_for_in_progress_pledges(client, monkeypatch):
    """In-progress pledges should render their progress treatment on the homepage."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(
                pledge_status="partial",
                display_status="In progress",
                allocated_quantity_kg=700,
                remaining_quantity_kg=800,
                fulfillment_percent=46.7,
            )
        ],
    )

    response = client.get("/buyer-pledges")

    assert b"46.7%" in response.data
    assert b"Fulfilment progress" in response.data


def test_buyer_pledges_page_filters_rows_by_search_and_crop(client, monkeypatch):
    """Search and crop filters should narrow the visible pledge list."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(organisation_name="Alpha Foods", crop_type="Beans"),
            make_pledge(buyer_pledge_id=2, organisation_name="Beta Markets", crop_type="Tomatoes"),
        ],
    )

    response = client.get("/buyer-pledges?q=beta&crop=Tomatoes")

    assert b"Beta Markets" in response.data
    assert b"Alpha Foods" not in response.data


def test_buyer_pledges_page_renders_empty_state_when_filters_remove_all_rows(client, monkeypatch):
    """An empty filter result should keep the page structure and show an empty state."""
    monkeypatch.setattr(app_module, "get_all_buyer_pledges", lambda: [])

    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"No buyer pledges match the current filters." in response.data
    assert b"Select a buyer pledge from the table to review its details and next steps." in response.data
