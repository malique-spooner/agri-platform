"""Tests for the farm directory page."""

from __future__ import annotations

import sqlite3

import app as app_module


def test_farms_page_returns_success(client):
    """The farm directory page should return HTTP 200."""
    response = client.get("/farms")

    assert response.status_code == 200
    assert b"Registered Farms" in response.data
    assert b"<table" in response.data
    assert b"View farm" in response.data
    assert b"Register farmer" in response.data
    assert b'href="/farmers/register"' in response.data


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
                "crop_types": ["Robusta Coffee"],
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
                "crop_types": ["Arabica Coffee"],
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
                "crop_types": ["Robusta Coffee"],
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
                "crop_types": ["Arabica Coffee"],
                "next_available_date": "2026-07-01",
                "has_active_offers": True,
                "available_soon": False,
            },
        ],
    )

    response = client.get("/farms?crop=Arabica Coffee")

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
                "crop_types": ["Arabica Coffee", "Robusta Coffee"],
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
                "crop_types": ["Arabica Coffee"],
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
    assert b"Crop offers" in response.data
    assert b"Location" in response.data
    assert b"farm-map" in response.data
    assert b"leaflet" in response.data.lower()
    assert b"View offer" in response.data


def test_farm_pledge_detail_page_returns_success(client, monkeypatch):
    """A valid farm crop-offer detail page should render pledge-specific crop records."""
    monkeypatch.setattr(
        app_module,
        "get_farm_by_id",
        lambda farm_id: {
            "farmer_account_id": farm_id,
            "farm_name": "Sipi Plot",
            "farmer_name": "Grace Namukolo",
            "county": "Mbale",
            "region": "Uganda",
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledge_by_id",
        lambda farm_id, pledge_id: {
            "farmer_pledge_id": pledge_id,
            "farmer_account_id": farm_id,
            "crop_type": "Arabica Coffee",
            "quantity_kg": 400,
            "allocated_quantity_kg": 0,
            "remaining_quantity_kg": 400,
            "asking_price_per_kg": 2.0,
            "available_from_date": "2026-06-01",
            "pledge_status": "available",
        },
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge", lambda *_: [])
    monkeypatch.setattr(app_module, "get_input_catalog_entries", lambda: [])

    response = client.get("/farms/1/pledges/1")

    assert response.status_code == 200
    assert b"Offer Details" in response.data
    assert b"Add input record" in response.data
    assert b"Input history" in response.data
    assert b"Category" in response.data
    assert b"Product" in response.data
    assert b"Brand" in response.data
    assert b"Method" in response.data


def test_farm_pledge_detail_page_can_add_input_log_from_catalog(client, test_database_path):
    """The crop-offer page should allow adding a crop record from the active catalog."""
    with sqlite3.connect(test_database_path) as connection:
        farm_id, pledge_id, catalog_id = connection.execute(
            """
            SELECT fa.farmer_account_id, fp.farmer_pledge_id, ic.input_catalog_id
            FROM farmer_accounts AS fa
            INNER JOIN farmer_pledges AS fp
                ON fa.farmer_account_id = fp.farmer_account_id
            CROSS JOIN input_catalog AS ic
            LEFT JOIN pledge_allocations AS pa
                ON fp.farmer_pledge_id = pa.farmer_pledge_id
            WHERE ic.is_active = 1
            GROUP BY fa.farmer_account_id, fp.farmer_pledge_id, ic.input_catalog_id, fp.quantity_kg
            HAVING fp.pledge_status IN ('available', 'partial')
               AND fp.quantity_kg - COALESCE(SUM(pa.allocated_quantity_kg), 0) > 0
            LIMIT 1
            """
        ).fetchone()
        before_count = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE farmer_account_id = ? AND farmer_pledge_id = ?",
            (farm_id, pledge_id),
        ).fetchone()[0]

    response = client.post(
        f"/farms/{farm_id}/pledges/{pledge_id}",
        data={
            "action": "add_input_log",
            "input_catalog_id": str(catalog_id),
            "quantity": "12",
            "log_date": "2026-04-20",
            "notes": "Field inspection entry",
        },
    )

    assert response.status_code == 200
    assert b"Added" in response.data
    with sqlite3.connect(test_database_path) as connection:
        after_count = connection.execute(
            "SELECT COUNT(*) FROM farm_input_logs WHERE farmer_account_id = ? AND farmer_pledge_id = ?",
            (farm_id, pledge_id),
        ).fetchone()[0]
        log_row = connection.execute(
            """
            SELECT input_catalog_id, quantity, log_date, notes
            FROM farm_input_logs
            WHERE farmer_account_id = ? AND farmer_pledge_id = ?
            ORDER BY input_log_id DESC
            LIMIT 1
            """,
            (farm_id, pledge_id),
        ).fetchone()

    assert after_count == before_count + 1
    assert log_row[0] == catalog_id
    assert float(log_row[1]) == 12.0
    assert log_row[2] == "2026-04-20"
    assert log_row[3] == "Field inspection entry"


def test_farm_pledge_detail_page_hides_input_form_when_allocated(client, monkeypatch):
    """Allocated crop offers should render without the add-input form."""
    monkeypatch.setattr(
        app_module,
        "get_farm_by_id",
        lambda farm_id: {
            "farmer_account_id": farm_id,
            "farm_name": "Sipi Plot",
            "farmer_name": "Grace Namukolo",
            "county": "Mbale",
            "region": "Uganda",
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledge_by_id",
        lambda farm_id, pledge_id: {
            "farmer_pledge_id": pledge_id,
            "farmer_account_id": farm_id,
            "crop_type": "Arabica Coffee",
            "quantity_kg": 400,
            "allocated_quantity_kg": 400,
            "remaining_quantity_kg": 0,
            "asking_price_per_kg": 2.0,
            "available_from_date": "2026-06-01",
            "pledge_status": "allocated",
        },
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge", lambda *_: [])
    monkeypatch.setattr(app_module, "get_input_catalog_entries", lambda: [])

    response = client.get("/farms/1/pledges/1")

    assert response.status_code == 200
    assert b"Add input record" not in response.data
    assert b"Records locked" in response.data


def test_farm_pledge_detail_page_blocks_input_log_submission_when_allocated(client, monkeypatch):
    """Allocated crop offers should reject new crop input submissions."""
    monkeypatch.setattr(
        app_module,
        "get_farm_by_id",
        lambda farm_id: {
            "farmer_account_id": farm_id,
            "farm_name": "Sipi Plot",
            "farmer_name": "Grace Namukolo",
            "county": "Mbale",
            "region": "Uganda",
        },
    )
    monkeypatch.setattr(
        app_module,
        "get_farmer_pledge_by_id",
        lambda farm_id, pledge_id: {
            "farmer_pledge_id": pledge_id,
            "farmer_account_id": farm_id,
            "crop_type": "Arabica Coffee",
            "quantity_kg": 400,
            "allocated_quantity_kg": 400,
            "remaining_quantity_kg": 0,
            "asking_price_per_kg": 2.0,
            "available_from_date": "2026-06-01",
            "pledge_status": "allocated",
        },
    )
    monkeypatch.setattr(app_module, "get_input_logs_for_pledge", lambda *_: [])
    monkeypatch.setattr(app_module, "get_input_catalog_entries", lambda: [])

    response = client.post(
        "/farms/1/pledges/1",
        data={
            "action": "add_input_log",
            "input_catalog_id": "1",
            "quantity": "12",
            "log_date": "2026-04-20",
            "notes": "Field inspection entry",
        },
    )

    assert response.status_code == 200
    assert b"crop input records are locked" in response.data.lower()


def test_farm_pledge_detail_page_returns_404_for_unknown_pledge(client):
    """An unknown pledge id for a valid farm should return HTTP 404."""
    response = client.get("/farms/1/pledges/999999")

    assert response.status_code == 404


def test_farm_profile_page_returns_404_for_unknown_farm(client):
    """An unknown farm id should return HTTP 404."""
    response = client.get("/farms/999999")

    assert response.status_code == 404
