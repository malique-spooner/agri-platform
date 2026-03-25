"""Allocation helper functions for the server-rendered draft allocation workflow."""

from __future__ import annotations

from typing import Any


def criterion_label(criterion: dict[str, Any]) -> str:
    """Return a readable description for one buyer input rule."""
    parts = [str(criterion.get("input_type") or "").strip()]
    if criterion.get("product_name"):
        parts.append(str(criterion["product_name"]).strip())
    if criterion.get("brand_name"):
        parts.append(str(criterion["brand_name"]).strip())
    return " · ".join([part for part in parts if part])


def log_matches_criterion(log: dict[str, Any], criterion: dict[str, Any]) -> bool:
    """Return whether an input log satisfies a buyer criterion item."""
    if criterion.get("input_type") and str(log.get("input_type")) != str(criterion.get("input_type")):
        return False
    if criterion.get("product_name") and str(log.get("product_name")) != str(criterion.get("product_name")):
        return False
    if criterion.get("brand_name") and str(log.get("brand_name")) != str(criterion.get("brand_name")):
        return False
    return True


def enrich_eligible_pledges_with_criteria(
    buyer_criteria: dict[str, Any],
    eligible_pledges: list[dict[str, Any]],
    logs_by_pledge_id: dict[int, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    """Attach buyer-rule compatibility data to eligible crop offers."""
    required_inputs = buyer_criteria.get("required_inputs", [])
    blocked_inputs = buyer_criteria.get("blocked_inputs", [])
    enriched_pledges: list[dict[str, Any]] = []

    for pledge in eligible_pledges:
        pledge_id = int(pledge["farmer_pledge_id"])
        input_logs = logs_by_pledge_id.get(pledge_id, [])
        missing_required = [
            criterion_label(criterion)
            for criterion in required_inputs
            if not any(log_matches_criterion(log, criterion) for log in input_logs)
        ]
        matched_required = [
            criterion_label(criterion)
            for criterion in required_inputs
            if any(log_matches_criterion(log, criterion) for log in input_logs)
        ]
        blocked_matches = [
            criterion_label(criterion)
            for criterion in blocked_inputs
            if any(log_matches_criterion(log, criterion) for log in input_logs)
        ]
        recent_inputs = []
        for log in input_logs[:3]:
            recent_inputs.append(criterion_label(log))

        if blocked_matches:
            criteria_status = "blocked"
            criteria_message = "Contains buyer-blocked input"
        elif missing_required:
            criteria_status = "review"
            criteria_message = "Missing one or more required practices"
        else:
            criteria_status = "eligible"
            criteria_message = "Matches current buyer rules"

        enriched_pledges.append(
            {
                **pledge,
                "input_logs": input_logs,
                "recent_inputs": recent_inputs,
                "matched_required": matched_required,
                "missing_required": missing_required,
                "blocked_matches": blocked_matches,
                "criteria_status": criteria_status,
                "criteria_message": criteria_message,
                "is_selectable": criteria_status == "eligible",
            }
        )

    return enriched_pledges


def build_draft_allocation(
    buyer_pledge: dict[str, Any],
    eligible_pledges: list[dict[str, Any]],
    submitted_quantities: dict[int, str],
) -> dict[str, Any]:
    """Return a validated draft allocation summary from submitted pledge quantities."""
    errors: list[str] = []
    selected_rows: list[dict[str, Any]] = []
    total_allocated = 0.0
    buyer_remaining = float(buyer_pledge.get("remaining_quantity_kg") or 0)
    eligible_by_id = {
        int(pledge["farmer_pledge_id"]): pledge
        for pledge in eligible_pledges
    }

    for pledge_id, raw_quantity in submitted_quantities.items():
        if raw_quantity.strip() == "":
            continue

        try:
            quantity = float(raw_quantity)
        except ValueError:
            errors.append(f"Allocation quantity for pledge {pledge_id} must be a number.")
            continue

        if quantity <= 0:
            continue

        pledge = eligible_by_id.get(pledge_id)
        if pledge is None:
            errors.append(f"Pledge {pledge_id} is not eligible for this buyer request.")
            continue

        if not pledge.get("is_selectable", True):
            errors.append(f"{pledge['farm_name']} does not currently satisfy the buyer criteria.")
            continue

        available_quantity = float(pledge.get("available_quantity_kg") or 0)
        if quantity > available_quantity:
            errors.append(
                f"{pledge['farm_name']} can only contribute up to {available_quantity:.0f} kg."
            )
            continue

        selected_rows.append(
            {
                **pledge,
                "draft_quantity_kg": quantity,
            }
        )
        total_allocated += quantity

    if total_allocated > buyer_remaining:
        errors.append(
            f"Draft allocation exceeds buyer remaining demand by {total_allocated - buyer_remaining:.0f} kg."
        )

    selected_rows.sort(
        key=lambda row: (
            str(row.get("farm_name", "")).lower(),
            int(row.get("farmer_pledge_id", 0)),
        )
    )
    remaining_after = max(buyer_remaining - total_allocated, 0)

    return {
        "selected_rows": selected_rows,
        "total_allocated_kg": total_allocated,
        "remaining_after_kg": remaining_after,
        "is_complete": total_allocated >= buyer_remaining and buyer_remaining > 0 and not errors,
        "errors": errors,
    }


def suggested_allocation_quantity(
    buyer_remaining_kg: float,
    available_quantity_kg: float,
) -> float:
    """Return the default allocation quantity for a single add action."""
    if buyer_remaining_kg <= 0 or available_quantity_kg <= 0:
        return 0.0
    return min(buyer_remaining_kg, available_quantity_kg)
