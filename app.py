"""Minimal Flask application for the agricultural coordination prototype."""

import logging
from typing import Any

from flask import Flask, abort, redirect, render_template, request, url_for

from logic.database_helpers import (
    get_all_buyer_pledges,
    get_all_farms,
    get_farm_by_id,
    get_farmer_pledge_by_id,
    get_farmer_pledges_for_farm,
    get_input_logs_for_pledge,
)
from logic.logging_config import configure_logging


configure_logging()
logger = logging.getLogger(__name__)


def group_buyer_pledges_by_status(pledges: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """Group buyer pledges into presentation sections."""
    grouped_pledges = {
        "open": [],
        "partial": [],
        "fulfilled": [],
    }

    for pledge in pledges:
        status = str(pledge.get("pledge_status", "")).lower()
        grouped_pledges.setdefault(status, []).append(pledge)

    return grouped_pledges


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
        pledges = get_all_buyer_pledges()
        grouped_pledges = group_buyer_pledges_by_status(pledges)
        logger.info("Rendering buyer pledges page with %s pledge(s)", len(pledges))
        return render_template(
            "buyer_pledges.html",
            pledges=pledges,
            open_pledges=grouped_pledges["open"],
            partial_pledges=grouped_pledges["partial"],
            fulfilled_pledges=grouped_pledges["fulfilled"],
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
