"""Tests for the settings page."""

from __future__ import annotations

import sqlite3


def test_settings_page_returns_success(client):
    """The settings page should render the standardized input catalog."""
    response = client.get("/settings")

    assert response.status_code == 200
    assert b"Input Catalog" in response.data
    assert b"Catalog entry" in response.data


def test_settings_page_can_add_catalog_entry(client, test_database_path):
    """Posting a new standardized input should persist it in the catalog."""
    response = client.post(
        "/settings",
        data={
            "action": "add",
            "input_category": "Pesticide",
            "product_name": "Sulphur dust",
            "brand_name": "FieldPure",
            "application_method": "Dusting",
            "default_unit": "kg",
            "compliance_tag": "restricted",
            "notes": "",
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Input catalog entry added." in response.data
    with sqlite3.connect(test_database_path) as connection:
        created_count = connection.execute(
            "SELECT COUNT(*) FROM input_catalog WHERE product_name = 'Sulphur dust'"
        ).fetchone()[0]

    assert created_count == 1


def test_settings_page_deactivates_used_catalog_entry(client, test_database_path):
    """Removing a referenced input should mark it inactive instead of deleting it."""
    with sqlite3.connect(test_database_path) as connection:
        input_catalog_id = connection.execute(
            """
            SELECT input_catalog_id
            FROM farm_input_logs
            WHERE input_catalog_id IS NOT NULL
            LIMIT 1
            """
        ).fetchone()[0]

    response = client.post(
        "/settings",
        data={"action": "remove", "input_catalog_id": input_catalog_id},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"marked inactive" in response.data
    with sqlite3.connect(test_database_path) as connection:
        is_active = connection.execute(
            "SELECT is_active FROM input_catalog WHERE input_catalog_id = ?",
            (input_catalog_id,),
        ).fetchone()[0]

    assert is_active == 0


def test_settings_page_can_reset_database(client, test_database_path):
    """Resetting the demo database should rebuild the seeded dataset."""
    with sqlite3.connect(test_database_path) as connection:
        connection.execute("DELETE FROM buyer_accounts")
        connection.commit()

    response = client.post(
        "/settings",
        data={"action": "reset_database"},
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Demo database reset successfully." in response.data
    with sqlite3.connect(test_database_path) as connection:
        buyer_count = connection.execute("SELECT COUNT(*) FROM buyer_accounts").fetchone()[0]

    assert buyer_count == 20
