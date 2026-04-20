"""Minimal Flask application for the agricultural coordination prototype."""

from datetime import date, timedelta
from io import BytesIO
import json
import logging
import os
from types import SimpleNamespace
from typing import Any

from flask import Flask, abort, redirect, render_template, request, send_file, session, url_for

from database.generate_data import generate_dataset
from logic.allocation_logic import (
    build_draft_allocation,
    enrich_eligible_pledges_with_criteria,
    suggested_allocation_quantity,
)
from logic.database_helpers import (
    create_input_catalog_entry,
    create_buyer_export_lot,
    create_farm_crop_record,
    get_all_buyer_pledges,
    get_all_farms,
    get_buyer_pledge_by_id,
    get_database_path,
    get_farm_by_id,
    get_farmer_pledge_by_id,
    get_farmer_pledges_for_crop,
    get_farmer_pledges_for_farm,
    get_input_catalog_entries,
    get_input_catalog_entry_by_id,
    get_crop_records_for_pledge,
    get_crop_records_for_pledge_ids,
    persist_confirmed_allocation,
    remove_input_catalog_entry,
    register_farmer_account,
)
from logic.logging_config import configure_logging
from logic.reporting import build_buyer_summary_pdf, build_farmer_summary_pdf


configure_logging()
logger = logging.getLogger(__name__)

# Backward-compatible aliases so existing tests and helpers can keep using the
# older names while the app code reads more cleanly.
create_farm_input_log = create_farm_crop_record
get_input_logs_for_pledge = get_crop_records_for_pledge
get_input_logs_for_pledge_ids = get_crop_records_for_pledge_ids


def buyer_status_filter_to_raw(status_filter: str) -> str:
    """Map presentation-facing status filters to stored status values."""
    return {
        "not_started": "open",
        "in_progress": "partial",
        "completed": "fulfilled",
    }.get(status_filter, "")


def buyer_pledge_sort_key(pledge: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    """Return a stable sort key for the buyer pledge queue."""
    deadline = pledge.get("needed_by_date") or "9999-12-31"
    status_priority = {"open": 0, "partial": 1, "fulfilled": 2}
    priority_key = (
        status_priority.get(str(pledge.get("pledge_status", "")).lower(), 99),
        deadline,
        -float(pledge.get("remaining_quantity_kg") or 0),
        str(pledge.get("organisation_name", "")).lower(),
    )

    if sort_by == "deadline":
        return (
            deadline,
            status_priority.get(str(pledge.get("pledge_status", "")).lower(), 99),
            -float(pledge.get("remaining_quantity_kg") or 0),
        )
    if sort_by == "remaining":
        return (
            -float(pledge.get("remaining_quantity_kg") or 0),
            deadline,
            str(pledge.get("organisation_name", "")).lower(),
        )
    if sort_by == "buyer":
        return (
            str(pledge.get("organisation_name", "")).lower(),
            deadline,
            int(pledge.get("buyer_pledge_id") or 0),
        )

    return priority_key


def filter_and_sort_buyer_pledges(
    pledges: list[dict[str, Any]],
    search_term: str,
    crop_filter: str,
    status_filter: str,
    sort_by: str,
) -> list[dict[str, Any]]:
    """Apply homepage filters and sorting to buyer pledges."""
    filtered_pledges = pledges

    if search_term:
        needle = search_term.casefold()
        filtered_pledges = [
            pledge
            for pledge in filtered_pledges
            if needle in str(pledge.get("organisation_name", "")).casefold()
            or needle in str(pledge.get("crop_type", "")).casefold()
        ]

    if crop_filter:
        filtered_pledges = [
            pledge for pledge in filtered_pledges if str(pledge.get("crop_type", "")) == crop_filter
        ]

    raw_status = buyer_status_filter_to_raw(status_filter)
    if raw_status:
        filtered_pledges = [
            pledge
            for pledge in filtered_pledges
            if str(pledge.get("pledge_status", "")).lower() == raw_status
        ]

    return sorted(filtered_pledges, key=lambda pledge: buyer_pledge_sort_key(pledge, sort_by))


def farm_sort_key(farm: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    """Return a stable sort key for the farm directory."""
    if sort_by == "supply":
        return (-float(farm.get("total_supply_kg") or 0), str(farm.get("farm_name", "")).lower())
    if sort_by == "offers":
        return (-int(farm.get("pledge_count") or 0), str(farm.get("farm_name", "")).lower())
    if sort_by == "next":
        next_available = farm.get("next_available_date") or "9999-12-31"
        return (next_available, str(farm.get("farm_name", "")).lower())
    if sort_by == "name":
        return (str(farm.get("farm_name", "")).lower(),)

    next_available = farm.get("next_available_date") or "9999-12-31"
    return (
        0 if farm.get("has_active_offers") else 1,
        next_available,
        -float(farm.get("total_supply_kg") or 0),
        str(farm.get("farm_name", "")).lower(),
    )


def filter_and_sort_farms(
    farms: list[dict[str, Any]],
    search_term: str,
    crop_filter: str,
    availability_filter: str,
    sort_by: str,
) -> list[dict[str, Any]]:
    """Apply lightweight directory filters and sorting."""
    filtered_farms = farms

    if search_term:
        needle = search_term.casefold()
        filtered_farms = [
            farm
            for farm in filtered_farms
            if needle in str(farm.get("farm_name", "")).casefold()
            or needle in str(farm.get("farmer_name", "")).casefold()
            or needle in str(farm.get("county", "")).casefold()
            or needle in str(farm.get("region", "")).casefold()
        ]

    if crop_filter:
        filtered_farms = [
            farm
            for farm in filtered_farms
            if crop_filter in farm.get("crop_types", [])
        ]

    if availability_filter == "has_offers":
        filtered_farms = [farm for farm in filtered_farms if farm.get("has_active_offers")]
    elif availability_filter == "soon":
        filtered_farms = [farm for farm in filtered_farms if farm.get("available_soon")]

    return sorted(filtered_farms, key=lambda farm: farm_sort_key(farm, sort_by))


def allocation_offer_sort_key(pledge: dict[str, Any], sort_by: str) -> tuple[Any, ...]:
    """Return a stable sort key for allocation offers."""
    availability = pledge.get("available_from_date") or "9999-12-31"
    price = float(pledge.get("asking_price_per_kg") or 999)
    quantity = -float(pledge.get("available_quantity_kg") or 0)
    status_priority = {"eligible": 0, "review": 1, "blocked": 2}
    base = (
        status_priority.get(str(pledge.get("criteria_status", "")), 9),
        availability,
        quantity,
        price,
        str(pledge.get("farm_name", "")).lower(),
    )
    if sort_by == "soonest":
        return (availability, status_priority.get(str(pledge.get("criteria_status", "")), 9), quantity)
    if sort_by == "quantity":
        return (quantity, availability, price)
    if sort_by == "price":
        return (price, availability, quantity)
    if sort_by == "farm":
        return (str(pledge.get("farm_name", "")).lower(), availability)
    return base


def filter_and_sort_allocation_offers(
    pledges: list[dict[str, Any]],
    *,
    country_filter: str,
    availability_filter: str,
    rule_filter: str,
    sort_by: str,
    hide_ineligible: bool,
) -> list[dict[str, Any]]:
    """Apply server-side filters to allocation offers."""
    today = date.today()
    filtered = pledges

    if country_filter:
        filtered = [pledge for pledge in filtered if str(pledge.get("region", "")) == country_filter]

    if availability_filter == "now":
        filtered = [
            pledge
            for pledge in filtered
            if not pledge.get("available_from_date") or str(pledge.get("available_from_date")) <= today.isoformat()
        ]
    elif availability_filter == "soon":
        filtered = [
            pledge
            for pledge in filtered
            if pledge.get("available_from_date")
            and str(pledge.get("available_from_date")) <= (today + timedelta(days=14)).isoformat()
        ]

    if rule_filter:
        filtered = [pledge for pledge in filtered if str(pledge.get("criteria_status", "")) == rule_filter]

    if hide_ineligible:
        filtered = [pledge for pledge in filtered if str(pledge.get("criteria_status", "")) != "blocked"]

    return sorted(filtered, key=lambda pledge: allocation_offer_sort_key(pledge, sort_by))


def auto_fill_allocation_quantities(
    current_quantities: dict[int, str],
    pledges: list[dict[str, Any]],
    remaining_after_kg: float,
) -> dict[int, str]:
    """Fill remaining buyer demand with the best available selectable offers."""
    updated_quantities = dict(current_quantities)
    remaining = float(remaining_after_kg)

    for pledge in pledges:
        if remaining <= 0:
            break
        if not pledge.get("is_selectable", True):
            continue

        pledge_id = int(pledge["farmer_pledge_id"])
        if pledge_id in updated_quantities:
            continue

        available_quantity = float(pledge.get("available_quantity_kg") or 0)
        quantity = min(remaining, available_quantity)
        if quantity <= 0:
            continue

        updated_quantities[pledge_id] = str(int(quantity) if quantity.is_integer() else round(quantity, 2))
        remaining -= quantity

    return updated_quantities


def buyer_pledge_is_actionable(pledge: dict[str, Any]) -> bool:
    """Return whether a buyer pledge still has demand that can be auto-allocated."""
    return float(pledge.get("remaining_quantity_kg") or 0) > 0 and str(pledge.get("pledge_status", "")).lower() in {
        "open",
        "partial",
    }


def build_auto_allocate_preview(
    buyer_pledge: dict[str, Any] | None,
) -> tuple[bool, str, float]:
    """Return whether the selected pledge can be auto-filled and submitted."""
    if buyer_pledge is None:
        return False, "Select an export lot to check auto-submit readiness.", 0.0

    if not buyer_pledge_is_actionable(buyer_pledge):
        return False, "This export lot is already complete.", 0.0

    raw_eligible_pledges = get_farmer_pledges_for_crop(str(buyer_pledge["crop_type"]))
    logs_by_pledge_id = get_input_logs_for_pledge_ids(
        [int(pledge["farmer_pledge_id"]) for pledge in raw_eligible_pledges]
    )
    eligible_pledges = enrich_eligible_pledges_with_criteria(
        buyer_criteria=buyer_pledge.get("criteria", {}),
        eligible_pledges=raw_eligible_pledges,
        logs_by_pledge_id=logs_by_pledge_id,
    )
    selectable_supply = sum(
        float(pledge.get("available_quantity_kg") or 0)
        for pledge in eligible_pledges
        if pledge.get("is_selectable", True)
    )
    remaining = float(buyer_pledge.get("remaining_quantity_kg") or 0)
    if selectable_supply < remaining:
        return (
            False,
            f"Only {selectable_supply:.0f} kg of eligible supply is available for {remaining:.0f} kg remaining.",
            selectable_supply,
        )
    return True, f"Auto-fill can fully submit this lot with {selectable_supply:.0f} kg of eligible supply.", selectable_supply


def auto_allocate_and_submit_buyer_pledge(pledge_id: int) -> tuple[bool, str]:
    """Auto-fill and persist a buyer pledge allocation in one step."""
    buyer_pledge = get_buyer_pledge_by_id(pledge_id)
    if buyer_pledge is None:
        logger.warning("Buyer pledge not found for auto-allocate-and-submit id=%s", pledge_id)
        return False, "Buyer pledge not found."

    ready, reason, _ = build_auto_allocate_preview(buyer_pledge)
    if not ready:
        logger.info(
            "Auto-allocate-and-submit rejected buyer pledge id=%s because it is not ready: %s",
            pledge_id,
            reason,
        )
        return False, reason

    raw_eligible_pledges = get_farmer_pledges_for_crop(str(buyer_pledge["crop_type"]))
    logs_by_pledge_id = get_input_logs_for_pledge_ids(
        [int(pledge["farmer_pledge_id"]) for pledge in raw_eligible_pledges]
    )
    eligible_pledges = enrich_eligible_pledges_with_criteria(
        buyer_criteria=buyer_pledge.get("criteria", {}),
        eligible_pledges=raw_eligible_pledges,
        logs_by_pledge_id=logs_by_pledge_id,
    )
    draft_allocation = build_draft_allocation(
        buyer_pledge=buyer_pledge,
        eligible_pledges=eligible_pledges,
        submitted_quantities={},
    )
    updated_quantities = auto_fill_allocation_quantities(
        {},
        eligible_pledges,
        float(draft_allocation["remaining_after_kg"]),
    )
    draft_allocation = build_draft_allocation(
        buyer_pledge=buyer_pledge,
        eligible_pledges=eligible_pledges,
        submitted_quantities=updated_quantities,
    )
    if draft_allocation["selected_rows"] and not draft_allocation["errors"]:
        persist_confirmed_allocation(
            buyer_pledge_id=int(buyer_pledge["buyer_pledge_id"]),
            selected_rows=draft_allocation["selected_rows"],
        )
        logger.info(
            "Auto-allocate-and-submit persisted buyer pledge id=%s with %s row(s)",
            buyer_pledge["buyer_pledge_id"],
            len(draft_allocation["selected_rows"]),
        )
        return True, "Auto-allocate and submit completed."

    logger.warning(
        "Auto-allocate-and-submit could not complete for buyer pledge id=%s because the draft was empty or invalid",
        buyer_pledge["buyer_pledge_id"],
    )
    return False, "Auto-fill staged the draft, but it could not be submitted."


def build_buyer_queue_summary(pledges: list[dict[str, Any]]) -> dict[str, float | int]:
    """Return high-level metrics for the buyer pledges dashboard."""
    total_quantity = sum(float(pledge.get("quantity_kg") or 0) for pledge in pledges)
    remaining_quantity = sum(float(pledge.get("remaining_quantity_kg") or 0) for pledge in pledges)
    return {
        "total_lots": len(pledges),
        "ready_lots": sum(1 for pledge in pledges if str(pledge.get("pledge_status", "")).lower() == "fulfilled"),
        "active_lots": sum(
            1
            for pledge in pledges
            if str(pledge.get("pledge_status", "")).lower() in {"open", "partial"}
        ),
        "total_quantity_kg": total_quantity,
        "remaining_quantity_kg": remaining_quantity,
    }


def catalog_entry_to_criterion(entry: dict[str, Any]) -> dict[str, Any]:
    """Convert a catalog row into buyer-criteria JSON."""
    return {
        "input_type": entry.get("input_category"),
        "product_name": entry.get("product_name"),
        "brand_name": entry.get("brand_name"),
    }


def parse_catalog_selection(
    selected_ids: list[str],
    catalog_entries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Map selected catalog ids to criteria payload entries, ignoring duplicates."""
    catalog_by_id = {str(entry["input_catalog_id"]): entry for entry in catalog_entries}
    criteria: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for selected_id in selected_ids:
        selected_id = str(selected_id)
        if selected_id in seen_ids:
            continue
        seen_ids.add(selected_id)
        entry = catalog_by_id.get(selected_id)
        if entry is not None:
            criteria.append(catalog_entry_to_criterion(entry))
    return criteria


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="pages")
    app.secret_key = (
        os.environ.get("TRN_FARMER_TRACE_SECRET_KEY")
        or os.environ.get("AGRI_PLATFORM_SECRET_KEY")
        or "trn-farmer-trace-dev-secret"
    )
    logger.info("Flask application created")

    @app.route("/")
    def home():
        """Redirect the homepage to the buyer pledge management view."""
        logger.info("Redirecting home page to buyer pledges")
        return redirect(url_for("buyer_pledges"))

    @app.route("/buyer-pledges", methods=["GET", "POST"])
    def buyer_pledges():
        """Render the buyer pledge listing page."""
        logger.info("Loading buyer pledges page")
        all_pledges = get_all_buyer_pledges()
        page_message = request.args.get("message", "").strip()
        selected_id = request.args.get("selected", "").strip()
        search_term = request.args.get("q", "").strip()
        crop_filter = request.args.get("crop", "").strip()
        status_filter = request.args.get("status", "").strip()
        sort_by = request.args.get("sort", "priority").strip() or "priority"
        logger.info(
            "Buyer pledge filters q=%r crop=%r status=%r sort=%r selected=%r",
            search_term,
            crop_filter,
            status_filter,
            sort_by,
            selected_id,
        )

        pledges = filter_and_sort_buyer_pledges(
            all_pledges,
            search_term=search_term,
            crop_filter=crop_filter,
            status_filter=status_filter,
            sort_by=sort_by,
        )
        selected_pledge = None
        if selected_id.isdigit():
            selected_pledge = next(
                (pledge for pledge in pledges if int(pledge.get("buyer_pledge_id", 0)) == int(selected_id)),
                None,
            )
        if selected_pledge is None and pledges:
            selected_pledge = pledges[0]

        auto_allocate_ready, auto_allocate_reason, auto_allocate_supply = build_auto_allocate_preview(selected_pledge)

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            selected_id = request.form.get("selected_pledge_id", "").strip() or selected_id
            if action == "auto_fill_and_submit":
                post_selected_pledge = selected_pledge
                if selected_id.isdigit():
                    post_selected_pledge = next(
                        (pledge for pledge in all_pledges if int(pledge.get("buyer_pledge_id", 0)) == int(selected_id)),
                        post_selected_pledge,
                    )
                post_ready, post_reason, _ = build_auto_allocate_preview(post_selected_pledge)
                if post_selected_pledge is None or not post_ready:
                    logger.info(
                        "Auto-allocate-and-submit blocked for selected buyer pledge id=%s: %s",
                        selected_id,
                        post_reason,
                    )
                    return redirect(
                        url_for(
                            "buyer_pledges",
                            selected=selected_id if selected_id.isdigit() else None,
                            message=post_reason,
                        )
                    )

                success, message = auto_allocate_and_submit_buyer_pledge(int(post_selected_pledge["buyer_pledge_id"]))
                return redirect(
                    url_for(
                        "buyer_pledges",
                        selected=post_selected_pledge["buyer_pledge_id"],
                        message=message,
                    )
                )

        crop_options = sorted({str(pledge.get("crop_type", "")) for pledge in all_pledges if pledge.get("crop_type")})
        dashboard_summary = build_buyer_queue_summary(all_pledges)
        logger.info("Rendering buyer pledges page with %s visible pledge(s)", len(pledges))
        return render_template(
            "buyer_pledges.html",
            pledges=pledges,
            selected_pledge=selected_pledge,
            crop_options=crop_options,
            search_term=search_term,
            crop_filter=crop_filter,
            status_filter=status_filter,
            sort_by=sort_by,
            dashboard_summary=dashboard_summary,
            page_message=page_message,
            auto_allocate_ready=auto_allocate_ready,
            auto_allocate_reason=auto_allocate_reason,
            auto_allocate_supply=auto_allocate_supply,
        )

    @app.route("/buyer-pledges/new", methods=["GET", "POST"])
    @app.route("/export-lots/new", methods=["GET", "POST"])
    def create_export_lot():
        """Render and process the export lot creation form."""
        logger.info("Loading export lot creation page")
        message = ""
        success = False
        created_pledge_id = None
        crop_options = ["Arabica Coffee", "Robusta Coffee"]
        catalog_entries = get_input_catalog_entries()

        if request.method == "POST":
            organisation_name = request.form.get("organisation_name", "").strip()
            contact_name = request.form.get("contact_name", "").strip()
            email = request.form.get("email", "").strip()
            phone = request.form.get("phone", "").strip()
            crop_type = request.form.get("crop_type", "").strip()
            quantity_raw = request.form.get("quantity_kg", "").strip()
            target_price_raw = request.form.get("target_price_per_kg", "").strip()
            needed_by_date = request.form.get("needed_by_date", "").strip()
            required_input_ids = request.form.getlist("required_input_ids")
            blocked_input_ids = request.form.getlist("blocked_input_ids")

            errors = []
            if not organisation_name:
                errors.append("Organisation name is required.")
            if not contact_name:
                errors.append("Contact name is required.")
            if not crop_type:
                errors.append("Crop type is required.")
            if not quantity_raw:
                errors.append("Quantity is required.")

            quantity_kg = None
            target_price_per_kg = None

            if quantity_raw:
                try:
                    quantity_kg = float(quantity_raw)
                    if quantity_kg <= 0:
                        errors.append("Quantity must be greater than zero.")
                except ValueError:
                    errors.append("Quantity must be a number.")

            if target_price_raw:
                try:
                    target_price_per_kg = float(target_price_raw)
                    if target_price_per_kg <= 0:
                        errors.append("Target price must be greater than zero.")
                except ValueError:
                    errors.append("Target price must be a number.")

            if needed_by_date:
                try:
                    date.fromisoformat(needed_by_date)
                except ValueError:
                    errors.append("Deadline must use YYYY-MM-DD format.")
            else:
                needed_by_date = None

            required_selection = {str(value) for value in required_input_ids if str(value).strip()}
            blocked_selection = {str(value) for value in blocked_input_ids if str(value).strip()}
            if required_selection & blocked_selection:
                errors.append("A catalog entry cannot be both required and blocked.")

            if errors:
                message = " ".join(errors)
                logger.warning("Export lot creation failed validation: %s", message)
            else:
                notes_payload = {
                    "priority": "standard",
                    "organic_preference": False,
                    "delivery_window_days": 14,
                    "required_inputs": parse_catalog_selection(required_input_ids, catalog_entries),
                    "blocked_inputs": parse_catalog_selection(blocked_input_ids, catalog_entries),
                }
                created_pledge_id = create_buyer_export_lot(
                    organisation_name=organisation_name,
                    contact_name=contact_name,
                    email=email or None,
                    phone=phone or None,
                    crop_type=crop_type,
                    quantity_kg=float(quantity_kg or 0),
                    target_price_per_kg=target_price_per_kg,
                    needed_by_date=needed_by_date,
                    notes=json.dumps(notes_payload, sort_keys=True),
                )
                success = True
                message = f"Export lot created for {organisation_name}."
                logger.info("Created new export lot id=%s for %s", created_pledge_id, organisation_name)

        return render_template(
            "export_lot_new.html",
            message=message,
            success=success,
            created_pledge_id=created_pledge_id,
            crop_options=crop_options,
            catalog_entries=catalog_entries,
        )

    @app.route("/buyer-pledges/<int:pledge_id>/allocation", methods=["GET", "POST"])
    def build_allocation(pledge_id: int):
        """Render a server-side draft allocation builder for one buyer pledge."""
        logger.info("Loading allocation builder for buyer pledge id=%s", pledge_id)
        buyer_pledge = get_buyer_pledge_by_id(pledge_id)
        if buyer_pledge is None:
            logger.warning("Buyer pledge not found for allocation builder id=%s", pledge_id)
            abort(404)

        raw_eligible_pledges = get_farmer_pledges_for_crop(str(buyer_pledge["crop_type"]))
        logs_by_pledge_id = get_input_logs_for_pledge_ids(
            [int(pledge["farmer_pledge_id"]) for pledge in raw_eligible_pledges]
        )
        eligible_pledges = enrich_eligible_pledges_with_criteria(
            buyer_criteria=buyer_pledge.get("criteria", {}),
            eligible_pledges=raw_eligible_pledges,
            logs_by_pledge_id=logs_by_pledge_id,
        )
        hide_ineligible_values = [value.strip() for value in request.args.getlist("hide_ineligible")]
        hide_ineligible = "1" in hide_ineligible_values or not hide_ineligible_values
        country_filter = request.args.get("country", "").strip()
        availability_filter = request.args.get("availability", "").strip()
        rule_filter = request.args.get("rule", "").strip()
        sort_by = request.args.get("sort", "priority").strip() or "priority"
        draft_session_key = f"draft_allocations:{pledge_id}"
        stored_quantities = {
            int(key): str(value)
            for key, value in session.get(draft_session_key, {}).items()
        }
        draft_allocation = build_draft_allocation(
            buyer_pledge=buyer_pledge,
            eligible_pledges=eligible_pledges,
            submitted_quantities=stored_quantities,
        )
        visible_pledges = filter_and_sort_allocation_offers(
            eligible_pledges,
            country_filter=country_filter,
            availability_filter=availability_filter,
            rule_filter=rule_filter,
            sort_by=sort_by,
            hide_ineligible=hide_ineligible,
        )
        country_options = sorted({str(pledge.get("region", "")) for pledge in eligible_pledges if pledge.get("region")})
        can_export_reports = (
            str(buyer_pledge.get("pledge_status", "")).lower() == "fulfilled"
            or float(buyer_pledge.get("remaining_quantity_kg") or 0) <= 0
        )
        submission_message = None
        if request.args.get("submitted") == "1":
            submission_message = "Allocation submitted."
        if request.args.get("auto_submitted") == "1":
            submission_message = "Auto-allocate and submit completed."

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            post_hide_ineligible_values = [value.strip() for value in request.form.getlist("hide_ineligible")]
            hide_ineligible = "1" in post_hide_ineligible_values
            country_filter = request.form.get("country", "").strip()
            availability_filter = request.form.get("availability", "").strip()
            rule_filter = request.form.get("rule", "").strip()
            sort_by = request.form.get("sort", "priority").strip() or "priority"
            logger.info(
                "Allocation builder action=%s for buyer pledge id=%s hide_ineligible=%s country=%r availability=%r rule=%r sort=%r",
                action,
                pledge_id,
                hide_ineligible,
                country_filter,
                availability_filter,
                rule_filter,
                sort_by,
            )

            if action == "add":
                selected_offer_id = request.form.get("selected_offer_id", "").strip()
                if selected_offer_id.isdigit():
                    offer_id = int(selected_offer_id)
                    selected_offer = next(
                        (pledge for pledge in eligible_pledges if int(pledge["farmer_pledge_id"]) == offer_id),
                        None,
                    )
                    if selected_offer is not None:
                        requested_quantity_raw = request.form.get("selected_quantity_kg", "").strip()
                        auto_quantity = suggested_allocation_quantity(
                            buyer_remaining_kg=float(draft_allocation["remaining_after_kg"]),
                            available_quantity_kg=float(selected_offer.get("available_quantity_kg") or 0),
                        )
                        selected_quantity = auto_quantity
                        if requested_quantity_raw:
                            try:
                                selected_quantity = float(requested_quantity_raw)
                            except ValueError:
                                selected_quantity = 0

                        max_allowed_quantity = min(
                            float(draft_allocation["remaining_after_kg"]),
                            float(selected_offer.get("available_quantity_kg") or 0),
                        )
                        if selected_quantity > max_allowed_quantity:
                            selected_quantity = max_allowed_quantity

                        if selected_quantity > 0:
                            stored_quantities[offer_id] = str(
                                int(selected_quantity) if float(selected_quantity).is_integer() else selected_quantity
                            )
                            submission_message = "Staged for submission."
                            logger.info(
                                "Staged farmer pledge id=%s for buyer pledge id=%s at %.2f kg",
                                offer_id,
                                pledge_id,
                                selected_quantity,
                            )
                        else:
                            submission_message = "No remaining demand is left to allocate for this buyer pledge."
                            logger.info(
                                "Skipped staging for buyer pledge id=%s because no remaining demand was available",
                                pledge_id,
                            )
                    else:
                        submission_message = "Selected crop offer is not available for this draft."
                        logger.warning(
                            "Rejected staging request for missing farmer pledge id=%s on buyer pledge id=%s",
                            selected_offer_id,
                            pledge_id,
                        )
            elif action == "remove":
                selected_offer_id = request.form.get("selected_offer_id", "").strip()
                if selected_offer_id.isdigit():
                    stored_quantities.pop(int(selected_offer_id), None)
                    logger.info(
                        "Removed staged farmer pledge id=%s from buyer pledge id=%s",
                        selected_offer_id,
                        pledge_id,
                    )
            elif action == "submit":
                if draft_allocation["selected_rows"] and not draft_allocation["errors"]:
                    persist_confirmed_allocation(
                        buyer_pledge_id=pledge_id,
                        selected_rows=draft_allocation["selected_rows"],
                    )
                    session.pop(draft_session_key, None)
                    return redirect(
                        url_for(
                            "build_allocation",
                            pledge_id=pledge_id,
                            hide_ineligible="1" if hide_ineligible else None,
                            country=country_filter or None,
                            availability=availability_filter or None,
                            rule=rule_filter or None,
                            sort=sort_by if sort_by != "priority" else None,
                            submitted="1",
                        )
                    )
                else:
                    submission_message = "Stage at least one valid farm contribution before submitting this allocation."
                    logger.warning(
                        "Rejected allocation submit for buyer pledge id=%s because draft was empty or invalid",
                        pledge_id,
                    )
            elif action == "auto_fill":
                updated_quantities = auto_fill_allocation_quantities(
                    stored_quantities,
                    visible_pledges,
                    float(draft_allocation["remaining_after_kg"]),
                )
                if updated_quantities == stored_quantities:
                    submission_message = "No additional eligible supply was available for auto-fill."
                    logger.info(
                        "Auto-fill made no changes for buyer pledge id=%s because no eligible supply remained",
                        pledge_id,
                    )
                else:
                    stored_quantities = updated_quantities
                    session[draft_session_key] = stored_quantities
                    draft_allocation = build_draft_allocation(
                        buyer_pledge=buyer_pledge,
                        eligible_pledges=eligible_pledges,
                        submitted_quantities=stored_quantities,
                    )
                    submission_message = "Auto-fill staged the remaining eligible supply."
                    logger.info(
                        "Auto-filled buyer pledge id=%s with %s staged row(s)",
                        pledge_id,
                        len(draft_allocation["selected_rows"]),
                    )
            elif action == "auto_fill_and_submit":
                updated_quantities = auto_fill_allocation_quantities(
                    stored_quantities,
                    visible_pledges,
                    float(draft_allocation["remaining_after_kg"]),
                )
                stored_quantities = updated_quantities
                session[draft_session_key] = stored_quantities
                draft_allocation = build_draft_allocation(
                    buyer_pledge=buyer_pledge,
                    eligible_pledges=eligible_pledges,
                    submitted_quantities=stored_quantities,
                )
                if draft_allocation["selected_rows"] and not draft_allocation["errors"]:
                    persist_confirmed_allocation(
                        buyer_pledge_id=pledge_id,
                        selected_rows=draft_allocation["selected_rows"],
                    )
                    session.pop(draft_session_key, None)
                    return redirect(
                        url_for(
                            "build_allocation",
                            pledge_id=pledge_id,
                            hide_ineligible="1" if hide_ineligible else None,
                            country=country_filter or None,
                            availability=availability_filter or None,
                            rule=rule_filter or None,
                            sort=sort_by if sort_by != "priority" else None,
                            submitted="1",
                            auto_submitted="1",
                        )
                    )
                submission_message = "Auto-fill staged the draft, but it could not be submitted."
                logger.warning(
                    "Auto-fill-and-submit could not complete for buyer pledge id=%s because the draft was empty or invalid",
                    pledge_id,
                )
            elif action in {"export_buyer_summary", "export_farm_summary"}:
                if not can_export_reports:
                    submission_message = "Complete the batch before exporting reports."
                    logger.warning(
                        "Rejected export action=%s for buyer pledge id=%s because batch is not complete",
                        action,
                        pledge_id,
                    )
                else:
                    logger.info("Generating export action=%s for buyer pledge id=%s", action, pledge_id)
                    if action == "export_buyer_summary":
                        pdf_bytes = build_buyer_summary_pdf(pledge_id)
                        filename = f"buyer-pledge-{pledge_id}-batch-summary.pdf"
                    else:
                        pdf_bytes = build_farmer_summary_pdf(pledge_id)
                        filename = f"buyer-pledge-{pledge_id}-farmer-summary.pdf"
                    return send_file(
                        BytesIO(pdf_bytes),
                        mimetype="application/pdf",
                        as_attachment=True,
                        download_name=filename,
                    )

            session[draft_session_key] = stored_quantities
            draft_allocation = build_draft_allocation(
                buyer_pledge=buyer_pledge,
                eligible_pledges=eligible_pledges,
                submitted_quantities=stored_quantities,
            )
            visible_pledges = filter_and_sort_allocation_offers(
                eligible_pledges,
                country_filter=country_filter,
                availability_filter=availability_filter,
                rule_filter=rule_filter,
                sort_by=sort_by,
                hide_ineligible=hide_ineligible,
            )
            logger.info(
                "Draft allocation updated for buyer pledge id=%s with %s selected pledge(s)",
                pledge_id,
                len(draft_allocation["selected_rows"]),
            )

        selected_offer_ids = {
            int(row["farmer_pledge_id"])
            for row in draft_allocation["selected_rows"]
        }
        for pledge in eligible_pledges:
            pledge["is_added"] = int(pledge["farmer_pledge_id"]) in selected_offer_ids
            pledge["suggested_quantity_kg"] = suggested_allocation_quantity(
                buyer_remaining_kg=float(draft_allocation["remaining_after_kg"]),
                available_quantity_kg=float(pledge.get("available_quantity_kg") or 0),
            )

        return render_template(
            "build_allocation.html",
            buyer_pledge=buyer_pledge,
            eligible_pledges=visible_pledges,
            draft_allocation=draft_allocation,
            hide_ineligible=hide_ineligible,
            country_filter=country_filter,
            availability_filter=availability_filter,
            rule_filter=rule_filter,
            sort_by=sort_by,
            country_options=country_options,
            submission_message=submission_message,
            can_export_reports=can_export_reports,
            active_database_path=str(get_database_path()),
        )

    @app.route("/farms")
    def farms():
        """Render the farm directory page."""
        logger.info("Loading farm directory page")
        all_farms = get_all_farms()
        search_term = request.args.get("q", "").strip()
        crop_filter = request.args.get("crop", "").strip()
        availability_filter = request.args.get("availability", "").strip()
        sort_by = request.args.get("sort", "priority").strip() or "priority"
        logger.info(
            "Farm directory filters q=%r crop=%r availability=%r sort=%r",
            search_term,
            crop_filter,
            availability_filter,
            sort_by,
        )
        farm_list = filter_and_sort_farms(
            all_farms,
            search_term=search_term,
            crop_filter=crop_filter,
            availability_filter=availability_filter,
            sort_by=sort_by,
        )
        crop_options = sorted({crop for farm in all_farms for crop in farm.get("crop_types", [])})
        logger.info("Rendering farm directory page with %s farm record(s)", len(farm_list))
        return render_template(
            "farms.html",
            farms=farm_list,
            crop_options=crop_options,
            search_term=search_term,
            crop_filter=crop_filter,
            availability_filter=availability_filter,
            sort_by=sort_by,
        )

    @app.route("/settings", methods=["GET", "POST"])
    def settings():
        """Render and manage the standardized input catalog."""
        if request.method == "POST":
            action = request.form.get("action", "").strip()
            category_filter = request.form.get("category_filter", "").strip()
            compliance_filter = request.form.get("compliance_filter", "").strip()
            include_inactive = request.form.get("include_inactive", "").strip() == "1"
            logger.info(
                "Settings action=%s category=%r compliance=%r include_inactive=%s",
                action,
                category_filter,
                compliance_filter,
                include_inactive,
            )
            message = ""

            if action == "add":
                input_category = request.form.get("input_category", "").strip()
                product_name = request.form.get("product_name", "").strip()
                application_method = request.form.get("application_method", "").strip()
                default_unit = request.form.get("default_unit", "").strip()
                compliance_tag = request.form.get("compliance_tag", "standard").strip()
                if input_category and product_name and application_method and default_unit:
                    create_input_catalog_entry(
                        input_category=input_category,
                        product_name=product_name,
                        brand_name=request.form.get("brand_name", "").strip() or None,
                        application_method=application_method,
                        default_unit=default_unit,
                        compliance_tag=compliance_tag,
                        notes=request.form.get("notes", "").strip() or None,
                    )
                    message = "Input catalog entry added."
                else:
                    message = "Add a category, product name, method, and default unit."
            elif action == "remove":
                selected_id = request.form.get("input_catalog_id", "").strip()
                if selected_id.isdigit():
                    removal_result = remove_input_catalog_entry(int(selected_id))
                    message = (
                        "Input removed from the catalog."
                        if removal_result == "deleted"
                        else "Input is already referenced, so it was marked inactive instead."
                    )
            elif action == "reset_database":
                logger.info("Resetting demo database from settings page")
                generate_dataset(
                    SimpleNamespace(
                        buyers=20,
                        buyer_pledges_total=20,
                        farmers=45,
                        max_buyer_pledges=2,
                        max_farmer_pledges=3,
                        max_input_logs=5,
                        seed=20260324,
                        database_path=get_database_path(),
                    )
                )
                session.clear()
                message = "Demo database reset successfully."

            return redirect(
                url_for(
                    "settings",
                    category=category_filter,
                    compliance=compliance_filter,
                    include_inactive="1" if include_inactive else None,
                    message=message or None,
                )
            )

        category_filter = request.args.get("category", "").strip()
        compliance_filter = request.args.get("compliance", "").strip()
        include_inactive = request.args.get("include_inactive", "").strip() == "1"
        catalog_entries = get_input_catalog_entries(
            category_filter=category_filter,
            compliance_filter=compliance_filter,
            include_inactive=include_inactive,
        )
        category_options = sorted({entry["input_category"] for entry in get_input_catalog_entries(include_inactive=True)})
        compliance_options = ["standard", "organic", "restricted"]
        logger.info("Rendering settings page with %s catalog entr(y/ies)", len(catalog_entries))
        return render_template(
            "settings.html",
            catalog_entries=catalog_entries,
            category_filter=category_filter,
            compliance_filter=compliance_filter,
            include_inactive=include_inactive,
            category_options=category_options,
            compliance_options=compliance_options,
            page_message=request.args.get("message", "").strip(),
        )

    @app.route("/farms/<int:farm_id>")
    def farm_profile(farm_id: int):
        """Render a single farm profile page."""
        logger.info("Loading farm profile page for farm id=%s", farm_id)
        farm = get_farm_by_id(farm_id)
        if farm is None:
            logger.warning("Farm profile not found for farm id=%s", farm_id)
            abort(404)

        pledges = get_farmer_pledges_for_farm(farm_id)
        logger.info(
            "Rendering farm profile page for farm id=%s with %s pledge(s)",
            farm_id,
            len(pledges),
        )
        return render_template(
            "farm_profile.html",
            farm=farm,
            pledges=pledges,
        )

    @app.route("/farms/<int:farm_id>/pledges/<int:pledge_id>", methods=["GET", "POST"])
    def farm_pledge_detail(farm_id: int, pledge_id: int):
        """Render a detailed page for one farm crop offer and its crop records."""
        logger.info("Loading farm pledge detail for farm id=%s pledge id=%s", farm_id, pledge_id)
        farm = get_farm_by_id(farm_id)
        if farm is None:
            logger.warning("Farm not found for farm id=%s when loading pledge detail", farm_id)
            abort(404)

        pledge = get_farmer_pledge_by_id(farm_id, pledge_id)
        if pledge is None:
            logger.warning("Pledge id=%s not found for farm id=%s", pledge_id, farm_id)
            abort(404)

        crop_records = get_input_logs_for_pledge(farm_id, pledge_id)
        input_catalog_entries = get_input_catalog_entries()
        message = ""
        success = False

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            if action == "add_input_log":
                selected_catalog_id = request.form.get("input_catalog_id", "").strip()
                quantity_raw = request.form.get("quantity", "").strip()
                log_date = request.form.get("log_date", "").strip()
                notes = request.form.get("notes", "").strip()

                errors = []
                if not selected_catalog_id.isdigit():
                    errors.append("Please choose an active catalog product.")
                if not quantity_raw:
                    errors.append("Quantity is required.")

                quantity = None
                if quantity_raw:
                    try:
                        quantity = float(quantity_raw)
                        if quantity <= 0:
                            errors.append("Quantity must be greater than zero.")
                    except ValueError:
                        errors.append("Quantity must be a number.")

                if not log_date:
                    log_date = date.today().isoformat()
                else:
                    try:
                        date.fromisoformat(log_date)
                    except ValueError:
                        errors.append("Log date must use YYYY-MM-DD format.")

                if errors:
                    message = " ".join(errors)
                    logger.warning(
                        "Crop record validation failed for farm id=%s pledge id=%s: %s",
                        farm_id,
                        pledge_id,
                        message,
                    )
                else:
                    catalog_entry = get_input_catalog_entry_by_id(int(selected_catalog_id))
                    if catalog_entry is None or not catalog_entry.get("is_active"):
                        message = "Please choose an active catalog product."
                        logger.warning(
                            "Rejected crop record creation for farm id=%s pledge id=%s because catalog entry was missing or inactive",
                            farm_id,
                            pledge_id,
                        )
                    else:
                        create_farm_input_log(
                            farmer_account_id=farm_id,
                            farmer_pledge_id=pledge_id,
                            input_catalog_id=int(selected_catalog_id),
                            quantity=float(quantity or 0),
                            log_date=log_date,
                            notes=notes or None,
                        )
                        crop_records = get_input_logs_for_pledge(farm_id, pledge_id)
                        success = True
                        message = f"Added {catalog_entry['product_name']} to this crop offer."
                        logger.info(
                            "Added crop record for farm id=%s pledge id=%s using catalog id=%s",
                            farm_id,
                            pledge_id,
                            selected_catalog_id,
                        )
        logger.info(
            "Rendering farm pledge detail for farm id=%s pledge id=%s with %s crop record(s)",
            farm_id,
            pledge_id,
            len(crop_records),
        )
        return render_template(
            "farm_pledge_detail.html",
            farm=farm,
            pledge=pledge,
            crop_records=crop_records,
            input_catalog_entries=input_catalog_entries,
            message=message,
            success=success,
            today_iso=date.today().isoformat(),
        )

    @app.route("/farmers/register", methods=["GET", "POST"])
    def register_farmer():
        """Render and process the farmer registration form."""
        logger.info("Loading farmer registration page")
        message = ""
        success = False

        if request.method == "POST":
            farm_name = request.form.get("farm_name", "").strip()
            farmer_name = request.form.get("farmer_name", "").strip()
            national_id = request.form.get("national_id", "").strip()
            phone = request.form.get("phone", "").strip()
            region = request.form.get("region", "").strip()
            county = request.form.get("county", "").strip()
            crop_type = request.form.get("crop_type", "").strip()
            plot_size_ha = request.form.get("plot_size_ha", "").strip()
            latitude_raw = request.form.get("latitude", "").strip()
            longitude_raw = request.form.get("longitude", "").strip()

            errors = []
            if not farm_name:
                errors.append("Farm name is required.")
            if not farmer_name:
                errors.append("Farmer name is required.")
            if not national_id:
                errors.append("National ID is required.")
            if not phone:
                errors.append("Phone number is required.")
            if not region:
                errors.append("Region is required.")
            if not county:
                errors.append("County is required.")
            if not crop_type:
                errors.append("Crop type is required.")

            latitude = None
            longitude = None
            plot_size = None

            if latitude_raw:
                try:
                    latitude = float(latitude_raw)
                except ValueError:
                    errors.append("Latitude must be a number.")

            if longitude_raw:
                try:
                    longitude = float(longitude_raw)
                except ValueError:
                    errors.append("Longitude must be a number.")

            if plot_size_ha:
                try:
                    plot_size = float(plot_size_ha)
                    if plot_size <= 0:
                        errors.append("Plot size must be greater than zero.")
                except ValueError:
                    errors.append("Plot size must be a number.")

            if errors:
                message = " ".join(errors)
                logger.warning("Farmer registration failed validation: %s", message)
            else:
                register_farmer_account(
                    farm_name=farm_name,
                    farmer_name=farmer_name,
                    national_id=national_id,
                    phone=phone,
                    region=region,
                    county=county,
                    crop_type=crop_type,
                    plot_size_ha=plot_size,
                    latitude=latitude,
                    longitude=longitude,
                )
                success = True
                message = f"{farmer_name} ({farm_name}) has been registered successfully."
                logger.info("Registered new farmer: %s at %s", farmer_name, farm_name)

        return render_template(
            "farmer_register.html",
            message=message,
            success=success,
        )

    return app


app = create_app()


if __name__ == "__main__":
    logger.info("Starting development server")
    app.run(
        host="0.0.0.0",
        port=int(os.environ.get("PORT", os.environ.get("TRN_FARMER_TRACE_PORT", 5000))),
        debug=True,
        use_reloader=False,
    )
