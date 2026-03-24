"""Minimal Flask application for the agricultural coordination prototype."""

import logging
import os
from typing import Any

from flask import Flask, abort, redirect, render_template, request, session, url_for

from logic.allocation_logic import (
    build_draft_allocation,
    enrich_eligible_pledges_with_criteria,
    suggested_allocation_quantity,
)
from logic.database_helpers import (
    get_all_buyer_pledges,
    get_all_farms,
    get_buyer_pledge_by_id,
    get_database_path,
    get_farm_by_id,
    get_farmer_pledge_by_id,
    get_farmer_pledges_for_crop,
    get_farmer_pledges_for_farm,
    get_input_logs_for_pledge,
    get_input_logs_for_pledge_ids,
    persist_confirmed_allocation,
)
from logic.logging_config import configure_logging


configure_logging()
logger = logging.getLogger(__name__)


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


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="pages")
    app.secret_key = os.environ.get("AGRI_PLATFORM_SECRET_KEY", "agri-platform-dev-secret")
    logger.info("Flask application created")

    @app.route("/")
    def home():
        """Redirect the homepage to the buyer pledge management view."""
        logger.info("Redirecting home page to buyer pledges")
        return redirect(url_for("buyer_pledges"))

    @app.route("/buyer-pledges")
    def buyer_pledges():
        """Render the buyer pledge listing page."""
        logger.info("Loading buyer pledges page")
        all_pledges = get_all_buyer_pledges()
        search_term = request.args.get("q", "").strip()
        crop_filter = request.args.get("crop", "").strip()
        status_filter = request.args.get("status", "").strip()
        sort_by = request.args.get("sort", "priority").strip() or "priority"
        selected_id = request.args.get("selected", "").strip()
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

        crop_options = sorted({str(pledge.get("crop_type", "")) for pledge in all_pledges if pledge.get("crop_type")})
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
        hide_ineligible = request.args.get("hide_ineligible", "").strip() == "1"
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
        submission_message = None
        if request.args.get("submitted") == "1":
            submission_message = "Allocation submitted to the SQLite database and the remaining demand has been refreshed."

        if request.method == "POST":
            action = request.form.get("action", "").strip()
            post_hide_ineligible = request.form.get("hide_ineligible", "").strip() == "1"
            hide_ineligible = post_hide_ineligible
            logger.info(
                "Allocation builder action=%s for buyer pledge id=%s hide_ineligible=%s",
                action,
                pledge_id,
                hide_ineligible,
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
                        auto_quantity = suggested_allocation_quantity(
                            buyer_remaining_kg=float(draft_allocation["remaining_after_kg"]),
                            available_quantity_kg=float(selected_offer.get("available_quantity_kg") or 0),
                        )
                        if auto_quantity > 0:
                            stored_quantities[offer_id] = str(int(auto_quantity) if auto_quantity.is_integer() else auto_quantity)
                            submission_message = "Added to draft batch."
                            logger.info(
                                "Staged farmer pledge id=%s for buyer pledge id=%s at %.2f kg",
                                offer_id,
                                pledge_id,
                                auto_quantity,
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
                            submitted="1",
                        )
                    )
                else:
                    submission_message = "Stage at least one valid farm contribution before submitting this allocation."
                    logger.warning(
                        "Rejected allocation submit for buyer pledge id=%s because draft was empty or invalid",
                        pledge_id,
                    )
            elif action in {"export_buyer_summary", "export_farm_summary"}:
                submission_message = "Export actions are shown here now and will be wired into real outputs next."
                logger.info("Placeholder export action=%s triggered for buyer pledge id=%s", action, pledge_id)

            session[draft_session_key] = stored_quantities
            draft_allocation = build_draft_allocation(
                buyer_pledge=buyer_pledge,
                eligible_pledges=eligible_pledges,
                submitted_quantities=stored_quantities,
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

        visible_pledges = [
            pledge
            for pledge in eligible_pledges
            if not hide_ineligible or pledge.get("is_selectable", True)
        ]

        return render_template(
            "build_allocation.html",
            buyer_pledge=buyer_pledge,
            eligible_pledges=visible_pledges,
            draft_allocation=draft_allocation,
            hide_ineligible=hide_ineligible,
            submission_message=submission_message,
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

    @app.route("/farms/<int:farm_id>/pledges/<int:pledge_id>")
    def farm_pledge_detail(farm_id: int, pledge_id: int):
        """Render a detailed page for one farm crop offer and its input logs."""
        logger.info("Loading farm pledge detail for farm id=%s pledge id=%s", farm_id, pledge_id)
        farm = get_farm_by_id(farm_id)
        if farm is None:
            logger.warning("Farm not found for farm id=%s when loading pledge detail", farm_id)
            abort(404)

        pledge = get_farmer_pledge_by_id(farm_id, pledge_id)
        if pledge is None:
            logger.warning("Pledge id=%s not found for farm id=%s", pledge_id, farm_id)
            abort(404)

        input_logs = get_input_logs_for_pledge(farm_id, pledge_id)
        logger.info(
            "Rendering farm pledge detail for farm id=%s pledge id=%s with %s input log(s)",
            farm_id,
            pledge_id,
            len(input_logs),
        )
        return render_template(
            "farm_pledge_detail.html",
            farm=farm,
            pledge=pledge,
            input_logs=input_logs,
        )

    return app


app = create_app()


if __name__ == "__main__":
    logger.info("Starting development server")
    app.run(debug=True)
