"""Tests for the buyer pledges page."""

from __future__ import annotations

import app as app_module


def test_buyer_pledges_page_returns_success(client):
    """The buyer pledges page should return HTTP 200."""
    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"Buyer Pledges" in response.data
    assert b"Open Demand" in response.data
    assert b"Partially Fulfilled" in response.data
    assert b"Fulfilled" in response.data


def test_buyer_pledges_page_renders_generated_status_sections(client):
    """The generated dataset should populate each buyer pledge status section."""
    response = client.get("/buyer-pledges")

    assert b"status-pill status-pill--open" in response.data
    assert b"status-pill status-pill--partial" in response.data
    assert b"status-pill status-pill--fulfilled" in response.data
    assert b"Fulfilment progress" in response.data


def test_buyer_pledges_page_renders_readable_criteria_summary(client):
    """Buyer criteria should render as readable text rather than raw JSON."""
    response = client.get("/buyer-pledges")

    assert b"Priority:" in response.data
    assert b"Organic preference:" in response.data
    assert b"Delivery window:" in response.data
    assert b'{"priority"' not in response.data


def test_buyer_pledges_page_orders_fulfilled_after_open_and_partial(client):
    """Open and partial demand should appear before fulfilled demand."""
    response_text = client.get("/buyer-pledges").get_data(as_text=True)

    open_position = response_text.find("Open Demand")
    partial_position = response_text.find("Partially Fulfilled")
    fulfilled_position = response_text.find("Fulfilled")

    assert open_position != -1
    assert partial_position != -1
    assert fulfilled_position != -1
    assert open_position < fulfilled_position
    assert partial_position < fulfilled_position


def test_buyer_pledges_page_uses_fallbacks_for_missing_price_and_deadline(client, monkeypatch):
    """Missing target price and deadline should render fallback text."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            {
                "buyer_pledge_id": 1,
                "organisation_name": "Test Buyer",
                "crop_type": "Beans",
                "quantity_kg": 1500,
                "target_price_per_kg": None,
                "needed_by_date": None,
                "pledge_status": "open",
                "notes": None,
                "criteria_summary": "No additional criteria recorded",
                "deadline_state": "unscheduled",
            }
        ],
    )

    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"TBC" in response.data
    assert b"No deadline set" in response.data
    assert b"No additional criteria recorded" in response.data


def test_buyer_pledges_page_renders_empty_sections_when_status_buckets_are_empty(client, monkeypatch):
    """Empty status buckets should still render visible empty-state messages."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            {
                "buyer_pledge_id": 1,
                "organisation_name": "Only Open Buyer",
                "crop_type": "Maize",
                "quantity_kg": 2000,
                "target_price_per_kg": 1.75,
                "needed_by_date": "2026-08-01",
                "pledge_status": "open",
                "notes": None,
                "criteria_summary": "No additional criteria recorded",
                "deadline_state": "scheduled",
            }
        ],
    )

    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"No partially fulfilled buyer pledges are available right now." in response.data
    assert b"No fulfilled buyer pledges are available right now." in response.data
