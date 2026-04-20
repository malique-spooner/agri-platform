"""Tests for the buyer pledges homepage."""

from __future__ import annotations

import sqlite3

import app as app_module


def make_pledge(**overrides):
    """Return a queue-ready buyer pledge fixture."""
    pledge = {
        "buyer_pledge_id": 1,
        "organisation_name": "Test Buyer",
        "crop_type": "Arabica Coffee",
        "quantity_kg": 1500,
        "allocated_quantity_kg": 0,
        "remaining_quantity_kg": 1500,
        "target_price_per_kg": 1.8,
        "needed_by_date": "2026-08-01",
        "pledge_status": "open",
        "display_status": "Not started",
        "criteria_summary": "Priority: standard | Organic preference: No | Delivery window: 7 days",
        "criteria": {
            "required_inputs": [
                {
                    "input_type": "Fertiliser",
                    "product_name": "NPK 17-17-17",
                    "brand_name": "GreenGrow",
                }
            ],
            "blocked_inputs": [
                {
                    "input_type": "Pesticide",
                    "product_name": "Pyrethrin spray",
                    "brand_name": "CropShield",
                }
            ],
        },
        "deadline_state": "scheduled",
        "fulfillment_percent": 0,
    }
    pledge.update(overrides)
    return pledge


def test_buyer_pledges_page_returns_success(client):
    """The buyer pledges page should return HTTP 200."""
    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"Export Lots" in response.data
    assert b"Add export lot" in response.data
    assert b"Total lots" in response.data
    assert b"Selected Pledge" in response.data
    assert b"Required" in response.data
    assert b"Blocked" in response.data
    assert b"Review eligible farms" in response.data
    assert b"Auto-allocate &amp; submit" in response.data
    assert b"/allocation" in response.data
    assert b'data-pledge-id="' in response.data


def test_buyer_pledges_page_auto_allocate_and_submit_returns_to_same_page(client, monkeypatch):
    """The one-click buyer-page action should redirect back to the buyer pledges page."""
    monkeypatch.setattr(
        app_module,
        "build_auto_allocate_preview",
        lambda buyer_pledge: (True, "Auto-fill can fully submit this lot with 1500 kg of eligible supply.", 1500),
    )
    monkeypatch.setattr(
        app_module,
        "auto_allocate_and_submit_buyer_pledge",
        lambda pledge_id: (True, f"Auto-allocate and submit completed for {pledge_id}."),
    )

    response = client.post(
        "/buyer-pledges",
        data={"action": "auto_fill_and_submit", "selected_pledge_id": "1473"},
        follow_redirects=False,
    )

    assert response.status_code == 302
    assert response.headers["Location"].startswith("/buyer-pledges?selected=")
    assert "message=Auto-allocate+and+submit+completed" in response.headers["Location"]


def test_auto_allocate_and_submit_buyer_pledge_submits_selected_actionable_pledge(client, monkeypatch):
    """A ready selected pledge should auto-fill and submit in one step."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(
                buyer_pledge_id=1473,
                organisation_name="Ready Buyer",
                crop_type="Arabica Coffee",
                pledge_status="open",
                display_status="Not started",
                allocated_quantity_kg=0,
                remaining_quantity_kg=1500,
                fulfillment_percent=0,
            ),
        ],
    )
    monkeypatch.setattr(
        app_module,
        "get_buyer_pledge_by_id",
        lambda pledge_id: make_pledge(
            buyer_pledge_id=pledge_id,
            organisation_name="Ready Buyer",
            crop_type="Arabica Coffee",
            pledge_status="open",
            display_status="Not started",
            allocated_quantity_kg=0,
            remaining_quantity_kg=1500,
            fulfillment_percent=0,
        ),
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
                "available_quantity_kg": 1500,
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
    monkeypatch.setattr(
        app_module,
        "enrich_eligible_pledges_with_criteria",
        lambda buyer_criteria, eligible_pledges, logs_by_pledge_id: eligible_pledges,
    )
    persisted = []

    def fake_persist_confirmed_allocation(buyer_pledge_id, selected_rows):
        persisted.append((buyer_pledge_id, selected_rows))

    monkeypatch.setattr(app_module, "persist_confirmed_allocation", fake_persist_confirmed_allocation)

    success, message = app_module.auto_allocate_and_submit_buyer_pledge(1473)

    assert success is True
    assert message == "Auto-allocate and submit completed."
    assert persisted
    assert persisted[0][0] == 1473


def test_buyer_pledges_page_greys_out_auto_submit_when_supply_is_insufficient(client, monkeypatch):
    """The buyer-page auto-submit button should disable when eligible supply cannot cover demand."""
    monkeypatch.setattr(
        app_module,
        "get_all_buyer_pledges",
        lambda: [
            make_pledge(
                buyer_pledge_id=1473,
                organisation_name="Hard Lot",
                crop_type="Arabica Coffee",
                pledge_status="open",
                display_status="Not started",
                remaining_quantity_kg=1500,
                quantity_kg=1500,
            )
        ],
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
                "available_quantity_kg": 250,
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
    monkeypatch.setattr(
        app_module,
        "enrich_eligible_pledges_with_criteria",
        lambda buyer_criteria, eligible_pledges, logs_by_pledge_id: eligible_pledges,
    )

    response = client.get("/buyer-pledges?selected=1473")

    assert response.status_code == 200
    assert b"Only 250 kg of eligible supply is available for 1500 kg remaining." in response.data
    assert b"disabled" in response.data


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
                crop_type="Arabica Coffee",
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
    assert "Arabica Coffee" in response_text
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
    assert b"None" in response.data


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
            make_pledge(organisation_name="Alpha Foods", crop_type="Arabica Coffee"),
            make_pledge(buyer_pledge_id=2, organisation_name="Beta Markets", crop_type="Robusta Coffee"),
        ],
    )

    response = client.get("/buyer-pledges?q=beta&crop=Robusta Coffee")

    assert b"Beta Markets" in response.data
    assert b"Alpha Foods" not in response.data


def test_buyer_pledges_page_renders_empty_state_when_filters_remove_all_rows(client, monkeypatch):
    """An empty filter result should keep the page structure and show an empty state."""
    monkeypatch.setattr(app_module, "get_all_buyer_pledges", lambda: [])

    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"No buyer pledges match the current filters." in response.data
    assert b"Select a buyer pledge from the table to review its details and next steps." in response.data


def test_export_lot_creation_page_returns_success(client):
    """The export lot creation page should render a buyer-demand form."""
    response = client.get("/export-lots/new")

    assert response.status_code == 200
    assert b"Create Export Lot" in response.data
    assert b"Create export lot" in response.data
    assert b"Quantity needed" in response.data
    assert b"Required inputs" in response.data
    assert b"Blocked inputs" in response.data


def test_export_lot_creation_page_can_create_a_new_lot(client, test_database_path):
    """Posting a new export lot should persist both buyer account and buyer pledge rows."""
    with sqlite3.connect(test_database_path) as connection:
        catalog_rows = [
            row
            for row in connection.execute(
                """
                SELECT input_catalog_id, product_name
                FROM input_catalog
                ORDER BY input_catalog_id
                LIMIT 2
                """
            ).fetchall()
        ]

    response = client.post(
        "/export-lots/new",
        data={
            "organisation_name": "Trace Roast Ltd",
            "contact_name": "Martha Wanjiku",
            "email": "ops@traceroast.example",
            "phone": "+254 700 123456",
            "crop_type": "Arabica Coffee",
            "quantity_kg": "900",
            "target_price_per_kg": "2.40",
            "needed_by_date": "2026-07-15",
            "required_input_ids": str(catalog_rows[0][0]),
            "blocked_input_ids": str(catalog_rows[1][0]),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"Export lot created for Trace Roast Ltd." in response.data
    with sqlite3.connect(test_database_path) as connection:
        lot_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM buyer_pledges AS bp
            INNER JOIN buyer_accounts AS ba
                ON bp.buyer_account_id = ba.buyer_account_id
            WHERE ba.organisation_name = 'Trace Roast Ltd'
            """
        ).fetchone()[0]
        notes = connection.execute(
            """
            SELECT bp.notes
            FROM buyer_pledges AS bp
            INNER JOIN buyer_accounts AS ba
                ON bp.buyer_account_id = ba.buyer_account_id
            WHERE ba.organisation_name = 'Trace Roast Ltd'
            """
        ).fetchone()[0]

    assert lot_count == 1
    assert "required_inputs" in notes
    assert "blocked_inputs" in notes
    assert catalog_rows[0][1] in notes
    assert catalog_rows[1][1] in notes


def test_export_lot_creation_page_rejects_overlap_between_required_and_blocked_rules(
    client, test_database_path
):
    """The export lot form should reject catalog entries that are both required and blocked."""
    with sqlite3.connect(test_database_path) as connection:
        catalog_id = connection.execute(
            """
            SELECT input_catalog_id
            FROM input_catalog
            WHERE is_active = 1
            LIMIT 1
            """
        ).fetchone()[0]

    response = client.post(
        "/export-lots/new",
        data={
            "organisation_name": "Overlap Buyer",
            "contact_name": "Grace Nanyonga",
            "email": "ops@overlap.example",
            "phone": "+256 700 000000",
            "crop_type": "Robusta Coffee",
            "quantity_kg": "700",
            "target_price_per_kg": "2.10",
            "needed_by_date": "2026-07-15",
            "required_input_ids": str(catalog_id),
            "blocked_input_ids": str(catalog_id),
        },
        follow_redirects=True,
    )

    assert response.status_code == 200
    assert b"cannot be both required and blocked" in response.data
    with sqlite3.connect(test_database_path) as connection:
        lot_count = connection.execute(
            """
            SELECT COUNT(*)
            FROM buyer_accounts
            WHERE organisation_name = 'Overlap Buyer'
            """
        ).fetchone()[0]

    assert lot_count == 0
