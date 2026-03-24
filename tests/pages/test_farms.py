"""Tests for the farm directory page."""

from __future__ import annotations

import app as app_module


def test_farms_page_returns_success(client):
    """The farm directory page should return HTTP 200."""
    response = client.get("/farms")

    assert response.status_code == 200
    assert b"Farm Directory" in response.data
    assert b"<table" in response.data
    assert b"View profile" in response.data


def test_farms_page_filters_by_search_term(client, monkeypatch):
    """Search should narrow the farm directory by name or region fields."""
    monkeypatch.setattr(
        app_module,
        "get_all_farms",
        lambda: [
            {
                "farmer_account_id": 1,
                "farm_name": "Sunrise Fields",
                "farmer_name": "Amina Njoroge",
                "county": "Nakuru",
                "region": "Kenya",
                "pledge_count": 2,
                "crop_count": 2,
                "total_supply_kg": 1200,
                "crop_types": ["Beans", "Tomatoes"],
                "next_available_date": "2026-06-01",
                "has_active_offers": True,
                "available_soon": True,
            },
            {
                "farmer_account_id": 2,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Morogoro",
                "region": "Tanzania",
                "pledge_count": 1,
                "crop_count": 1,
                "total_supply_kg": 800,
                "crop_types": ["Maize"],
                "next_available_date": "2026-07-01",
                "has_active_offers": True,
                "available_soon": False,
            },
        ],
    )

    response = client.get("/farms?q=nakuru")

    assert response.status_code == 200
    assert b"Sunrise Fields" in response.data
    assert b"Riverbend Farm" not in response.data


def test_farms_page_filters_by_crop(client, monkeypatch):
    """Crop filtering should keep only farms with matching crop types."""
    monkeypatch.setattr(
        app_module,
        "get_all_farms",
        lambda: [
            {
                "farmer_account_id": 1,
                "farm_name": "Sunrise Fields",
                "farmer_name": "Amina Njoroge",
                "county": "Nakuru",
                "region": "Kenya",
                "pledge_count": 2,
                "crop_count": 2,
                "total_supply_kg": 1200,
                "crop_types": ["Beans", "Tomatoes"],
                "next_available_date": "2026-06-01",
                "has_active_offers": True,
                "available_soon": True,
            },
            {
                "farmer_account_id": 2,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Morogoro",
                "region": "Tanzania",
                "pledge_count": 1,
                "crop_count": 1,
                "total_supply_kg": 800,
                "crop_types": ["Maize"],
                "next_available_date": "2026-07-01",
                "has_active_offers": True,
                "available_soon": False,
            },
        ],
    )

    response = client.get("/farms?crop=Maize")

    assert response.status_code == 200
    assert b"Riverbend Farm" in response.data
    assert b"Sunrise Fields" not in response.data


def test_farms_page_filters_by_availability(client, monkeypatch):
    """Availability filtering should return only farms available soon when requested."""
    monkeypatch.setattr(
        app_module,
        "get_all_farms",
        lambda: [
            {
                "farmer_account_id": 1,
                "farm_name": "Sunrise Fields",
                "farmer_name": "Amina Njoroge",
                "county": "Nakuru",
                "region": "Kenya",
                "pledge_count": 2,
                "crop_count": 2,
                "total_supply_kg": 1200,
                "crop_types": ["Beans", "Tomatoes"],
                "next_available_date": "2026-06-01",
                "has_active_offers": True,
                "available_soon": True,
            },
            {
                "farmer_account_id": 2,
                "farm_name": "Riverbend Farm",
                "farmer_name": "David Otieno",
                "county": "Morogoro",
                "region": "Tanzania",
                "pledge_count": 1,
                "crop_count": 1,
                "total_supply_kg": 800,
                "crop_types": ["Maize"],
                "next_available_date": "2026-07-01",
                "has_active_offers": True,
                "available_soon": False,
            },
        ],
    )

    response = client.get("/farms?availability=soon")

    assert response.status_code == 200
    assert b"Sunrise Fields" in response.data
    assert b"Riverbend Farm" not in response.data


def test_farms_page_renders_empty_state_when_filters_remove_all_results(client, monkeypatch):
    """An empty filter result should render a compact empty state."""
    monkeypatch.setattr(app_module, "get_all_farms", lambda: [])

    response = client.get("/farms")

    assert response.status_code == 200
    assert b"No farms match the current filters." in response.data


def test_farm_profile_page_returns_success(client):
    """A valid farm profile page should render details from the database."""
    response = client.get("/farms/1")

    assert response.status_code == 200
    assert b"Farm Profile" in response.data
    assert b"Production Pledges" in response.data
    assert b"Location" in response.data
    assert b"farm-map" in response.data
    assert b"leaflet" in response.data.lower()
    assert b"View crop details" in response.data


def test_farm_pledge_detail_page_returns_success(client):
    """A valid farm crop-offer detail page should render pledge-specific input history."""
    response = client.get("/farms/1/pledges/1")

    assert response.status_code == 200
    assert b"Offer Details" in response.data
    assert b"Input Log History" in response.data
    assert b"Category" in response.data
    assert b"Product" in response.data
    assert b"Brand" in response.data
    assert b"Method" in response.data


def test_farm_pledge_detail_page_returns_404_for_unknown_pledge(client):
    """An unknown pledge id for a valid farm should return HTTP 404."""
    response = client.get("/farms/1/pledges/999999")

    assert response.status_code == 404


def test_farm_profile_page_returns_404_for_unknown_farm(client):
    """An unknown farm id should return HTTP 404."""
    response = client.get("/farms/999999")

    assert response.status_code == 404
