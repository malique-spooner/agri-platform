"""PDF report generation for buyer and farmer allocation views."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from io import BytesIO
import json
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, StyleSheet1, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from logic.allocation_logic import criterion_label, log_matches_criterion
from logic.database_helpers import get_buyer_pledge_by_id, get_connection, get_input_logs_for_pledge_ids


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BRAND_MANIFEST_PATH = PROJECT_ROOT / "static" / "brand" / "atlas_harvest.json"


def load_brand_manifest() -> dict[str, Any]:
    """Return the current brand manifest or sensible fallbacks."""
    fallback = {
        "name": "Malique's Farm",
        "descriptor": "Coordination Console",
        "colors": {
            "ink": "#0F1724",
            "slate": "#5F6C7B",
            "orchardGreen": "#2F6E5B",
            "deepOrchard": "#234E41",
            "sageSignal": "#8FB8A7",
            "skyTint": "#B9D7F2",
            "wheatTint": "#E8D7AA",
            "roseAlert": "#D98A88",
            "cloudWhite": "#F9FBFD",
        },
    }
    if not BRAND_MANIFEST_PATH.exists():
        return fallback
    try:
        return json.loads(BRAND_MANIFEST_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return fallback


def build_styles(brand: dict[str, Any]) -> tuple[StyleSheet1, dict[str, colors.Color]]:
    """Create the report style palette."""
    palette = {
        "ink": colors.HexColor(brand["colors"]["ink"]),
        "slate": colors.HexColor(brand["colors"]["slate"]),
        "brand": colors.HexColor(brand["colors"]["orchardGreen"]),
        "brand_dark": colors.HexColor(brand["colors"]["deepOrchard"]),
        "brand_soft": colors.HexColor(brand["colors"]["sageSignal"]),
        "sky": colors.HexColor(brand["colors"]["skyTint"]),
        "wheat": colors.HexColor(brand["colors"]["wheatTint"]),
        "alert": colors.HexColor(brand["colors"]["roseAlert"]),
        "paper": colors.HexColor(brand["colors"]["cloudWhite"]),
    }
    styles = getSampleStyleSheet()
    styles["Title"].fontName = "Helvetica-Bold"
    styles["Title"].fontSize = 21
    styles["Title"].leading = 26
    styles["Title"].textColor = palette["ink"]
    styles["Title"].spaceAfter = 4

    styles.add(
        ParagraphStyle(
            name="ReportKicker",
            fontName="Helvetica-Bold",
            fontSize=8.5,
            leading=10,
            textColor=palette["brand"],
            spaceAfter=6,
            uppercase=True,
        )
    )
    styles.add(
        ParagraphStyle(
            name="ReportSubhead",
            fontName="Helvetica",
            fontSize=11,
            leading=16,
            textColor=palette["slate"],
            spaceAfter=14,
        )
    )
    styles.add(
        ParagraphStyle(
            name="SectionHeading",
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=palette["ink"],
            spaceBefore=8,
            spaceAfter=8,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Body",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=9.4,
            leading=13.5,
            textColor=palette["ink"],
            spaceAfter=4,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Muted",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=8.6,
            leading=12,
            textColor=palette["slate"],
            spaceAfter=3,
        )
    )
    styles.add(
        ParagraphStyle(
            name="Micro",
            parent=styles["BodyText"],
            fontName="Helvetica",
            fontSize=7.8,
            leading=10,
            textColor=palette["slate"],
        )
    )
    styles.add(
        ParagraphStyle(
            name="Value",
            fontName="Helvetica-Bold",
            fontSize=11.5,
            leading=14,
            textColor=palette["ink"],
        )
    )
    styles.add(
        ParagraphStyle(
            name="RightMeta",
            parent=styles["Micro"],
            alignment=TA_RIGHT,
        )
    )
    return styles, palette


def format_date(value: str | None) -> str:
    """Return a user-facing date string."""
    if not value:
        return "Not recorded"
    try:
        return datetime.fromisoformat(value.replace(" ", "T")).strftime("%d %b %Y")
    except ValueError:
        return value


def format_timestamp(value: str | None) -> str:
    """Return a user-facing timestamp string."""
    if not value:
        return "Not recorded"
    try:
        return datetime.fromisoformat(value.replace(" ", "T")).strftime("%d %b %Y, %H:%M")
    except ValueError:
        return value


def quantity_text(value: float | int | None) -> str:
    """Return a consistent quantity string."""
    if value is None:
        return "0 kg"
    number = float(value)
    if number.is_integer():
        return f"{int(number)} kg"
    return f"{number:.1f} kg"


def price_text(value: float | int | None) -> str:
    """Return a consistent price string."""
    if value is None:
        return "TBC"
    number = float(value)
    if number.is_integer():
        return f"{int(number)}"
    return f"{number:.2f}"


def criterion_lines(criteria_items: list[dict[str, Any]]) -> list[str]:
    """Return readable buyer-rule labels."""
    return [criterion_label(item) for item in criteria_items if criterion_label(item)]


def build_rule_snapshot(
    *,
    buyer_criteria: dict[str, Any],
    logs: list[dict[str, Any]],
) -> dict[str, list[str]]:
    """Return a report-friendly required/blocked snapshot for one pledge."""
    required_items = buyer_criteria.get("required_inputs", [])
    blocked_items = buyer_criteria.get("blocked_inputs", [])
    matched_required = [
        criterion_label(item)
        for item in required_items
        if any(log_matches_criterion(log, item) for log in logs)
    ]
    missing_required = [
        criterion_label(item)
        for item in required_items
        if not any(log_matches_criterion(log, item) for log in logs)
    ]
    blocked_matches = [
        criterion_label(item)
        for item in blocked_items
        if any(log_matches_criterion(log, item) for log in logs)
    ]
    return {
        "matched_required": matched_required,
        "missing_required": missing_required,
        "blocked_matches": blocked_matches,
    }


def fetch_batch_report_context(buyer_pledge_id: int) -> dict[str, Any]:
    """Return the buyer batch context used by both report perspectives."""
    buyer_pledge = get_buyer_pledge_by_id(buyer_pledge_id)
    if buyer_pledge is None:
        raise ValueError(f"Buyer pledge {buyer_pledge_id} was not found.")

    query = """
        SELECT
            bp.created_at AS buyer_pledge_created_at,
            ba.contact_name,
            ba.email AS buyer_email,
            ba.phone AS buyer_phone,
            pa.allocation_id,
            pa.allocated_quantity_kg,
            pa.allocation_status,
            pa.created_at AS allocation_created_at,
            fp.farmer_pledge_id,
            fp.crop_type AS farmer_crop_type,
            fp.quantity_kg AS farmer_total_quantity_kg,
            fp.asking_price_per_kg,
            fp.available_from_date,
            fp.pledge_status AS farmer_pledge_status,
            fp.created_at AS farmer_pledge_created_at,
            fa.farmer_account_id,
            fa.farm_name,
            fa.farmer_name,
            fa.county,
            fa.region,
            fa.latitude,
            fa.longitude,
            fa.email AS farm_email,
            fa.phone AS farm_phone,
            fa.total_hectares
        FROM buyer_pledges AS bp
        INNER JOIN buyer_accounts AS ba
            ON bp.buyer_account_id = ba.buyer_account_id
        LEFT JOIN pledge_allocations AS pa
            ON bp.buyer_pledge_id = pa.buyer_pledge_id
        LEFT JOIN farmer_pledges AS fp
            ON pa.farmer_pledge_id = fp.farmer_pledge_id
        LEFT JOIN farmer_accounts AS fa
            ON fp.farmer_account_id = fa.farmer_account_id
        WHERE bp.buyer_pledge_id = ?
        ORDER BY pa.created_at, pa.allocation_id
    """

    with get_connection() as connection:
        rows = [dict(row) for row in connection.execute(query, (buyer_pledge_id,)).fetchall()]

    batch_metadata = rows[0] if rows else {
        "buyer_pledge_created_at": buyer_pledge.get("created_at"),
        "contact_name": None,
        "buyer_email": None,
        "buyer_phone": None,
    }
    allocation_rows = [row for row in rows if row.get("allocation_id") is not None]
    pledge_ids = sorted({int(row["farmer_pledge_id"]) for row in allocation_rows})
    logs_by_pledge = get_input_logs_for_pledge_ids(pledge_ids)

    grouped_allocations: dict[tuple[int, int], dict[str, Any]] = {}
    for row in allocation_rows:
        key = (int(row["farmer_account_id"]), int(row["farmer_pledge_id"]))
        grouped_row = grouped_allocations.get(key)
        if grouped_row is None:
            logs = logs_by_pledge.get(int(row["farmer_pledge_id"]), [])
            grouped_row = {
                **row,
                "allocated_quantity_kg": float(row.get("allocated_quantity_kg") or 0),
                "allocation_created_at": row.get("allocation_created_at"),
                "allocation_ids": [int(row["allocation_id"])],
                "logs": logs,
                "rule_snapshot": build_rule_snapshot(
                    buyer_criteria=buyer_pledge.get("criteria", {}),
                    logs=logs,
                ),
            }
            grouped_allocations[key] = grouped_row
        else:
            grouped_row["allocated_quantity_kg"] += float(row.get("allocated_quantity_kg") or 0)
            grouped_row["allocation_ids"].append(int(row["allocation_id"]))
            latest_created_at = max(
                str(grouped_row.get("allocation_created_at") or ""),
                str(row.get("allocation_created_at") or ""),
            )
            grouped_row["allocation_created_at"] = latest_created_at or grouped_row.get("allocation_created_at")

    allocation_rows = sorted(
        grouped_allocations.values(),
        key=lambda row: (
            str(row.get("allocation_created_at") or ""),
            int(row.get("farmer_pledge_id") or 0),
        ),
    )

    farms: dict[int, dict[str, Any]] = {}
    for row in allocation_rows:
        farm_id = int(row["farmer_account_id"])
        farm_entry = farms.setdefault(
            farm_id,
            {
                "farmer_account_id": farm_id,
                "farm_name": row.get("farm_name"),
                "farmer_name": row.get("farmer_name"),
                "county": row.get("county"),
                "region": row.get("region"),
                "latitude": row.get("latitude"),
                "longitude": row.get("longitude"),
                "farm_email": row.get("farm_email"),
                "farm_phone": row.get("farm_phone"),
                "total_hectares": row.get("total_hectares"),
                "allocations": [],
                "total_allocated_kg": 0.0,
            },
        )
        farm_entry["allocations"].append(row)
        farm_entry["total_allocated_kg"] += float(row.get("allocated_quantity_kg") or 0)

    timeline = [
        {
            "timestamp": batch_metadata.get("buyer_pledge_created_at"),
            "label": "Buyer pledge created",
            "detail": f"{buyer_pledge['organisation_name']} requested {quantity_text(buyer_pledge['quantity_kg'])} of {buyer_pledge['crop_type']}.",
        }
    ]
    for row in allocation_rows:
        timeline.append(
            {
                "timestamp": row.get("allocation_created_at"),
                "label": "Contribution confirmed",
                "detail": f"{row['farm_name']} committed {quantity_text(row['allocated_quantity_kg'])} from offer #{row['farmer_pledge_id']}.",
            }
        )
    timeline.sort(key=lambda item: item["timestamp"] or "")

    return {
        "buyer_pledge": buyer_pledge,
        "batch_metadata": batch_metadata,
        "allocations": allocation_rows,
        "farms": list(farms.values()),
        "timeline": timeline,
        "generated_at": datetime.now().replace(microsecond=0),
    }


def report_header_footer(canvas, doc, brand: dict[str, Any], palette: dict[str, colors.Color]) -> None:
    """Draw the report chrome on every page."""
    canvas.saveState()
    width, height = A4
    canvas.setStrokeColor(palette["sky"])
    canvas.setLineWidth(0.6)
    canvas.line(doc.leftMargin, height - 16 * mm, width - doc.rightMargin, height - 16 * mm)
    canvas.line(doc.leftMargin, 14 * mm, width - doc.rightMargin, 14 * mm)
    canvas.setFillColor(palette["brand_dark"])
    canvas.setFont("Helvetica-Bold", 9)
    canvas.drawString(doc.leftMargin, height - 12 * mm, brand["name"])
    canvas.setFillColor(palette["slate"])
    canvas.setFont("Helvetica", 8)
    canvas.drawRightString(width - doc.rightMargin, height - 12 * mm, brand["descriptor"])
    canvas.drawString(doc.leftMargin, 9 * mm, "Agricultural coordination record")
    canvas.drawRightString(width - doc.rightMargin, 9 * mm, f"Page {canvas.getPageNumber()}")
    canvas.restoreState()


def stat_table(rows: list[tuple[str, str]], styles: StyleSheet1, palette: dict[str, colors.Color]) -> Table:
    """Return a compact two-column stat table."""
    table_rows = [
        [
            Paragraph(f"<b>{label}</b>", styles["Body"]),
            Paragraph(value, styles["Value"]),
        ]
        for label, value in rows
    ]
    table = Table(table_rows, colWidths=[58 * mm, 44 * mm], hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), palette["paper"]),
                ("BOX", (0, 0), (-1, -1), 0.35, palette["sky"]),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, palette["sky"]),
                ("LEFTPADDING", (0, 0), (-1, -1), 10),
                ("RIGHTPADDING", (0, 0), (-1, -1), 10),
                ("TOPPADDING", (0, 0), (-1, -1), 8),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ]
        )
    )
    return table


def simple_table(
    headers: list[str],
    rows: list[list[str]],
    *,
    styles: StyleSheet1,
    palette: dict[str, colors.Color],
    col_widths: list[float] | None = None,
) -> Table:
    """Return a styled report table."""
    data = [
        [Paragraph(f"<b>{header}</b>", styles["Muted"]) for header in headers],
        *[[Paragraph(str(cell), styles["Body"]) for cell in row] for row in rows],
    ]
    table = Table(data, colWidths=col_widths, repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), palette["paper"]),
                ("TEXTCOLOR", (0, 0), (-1, 0), palette["slate"]),
                ("LINEBELOW", (0, 0), (-1, 0), 0.6, palette["sky"]),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, palette["sky"]),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 7),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
            ]
        )
    )
    return table


def build_buyer_report_story(context: dict[str, Any], styles: StyleSheet1, palette: dict[str, colors.Color]) -> list[Any]:
    """Return the buyer-oriented report story."""
    buyer_pledge = context["buyer_pledge"]
    farms = context["farms"]
    allocations = context["allocations"]
    story: list[Any] = [
        Paragraph("Buyer batch report", styles["ReportKicker"]),
        Paragraph(f"Batch linked to pledge #{buyer_pledge['buyer_pledge_id']}", styles["Title"]),
        Paragraph(
            f"{buyer_pledge['organisation_name']} · {buyer_pledge['crop_type']} · generated {context['generated_at'].strftime('%d %b %Y, %H:%M')}",
            styles["ReportSubhead"],
        ),
        stat_table(
            [
                ("Required quantity", quantity_text(buyer_pledge["quantity_kg"])),
                ("Committed quantity", quantity_text(buyer_pledge["allocated_quantity_kg"])),
                ("Remaining demand", quantity_text(buyer_pledge["remaining_quantity_kg"])),
                ("Participating farms", str(len(farms))),
                ("Deadline", format_date(buyer_pledge.get("needed_by_date"))),
                ("Target price", price_text(buyer_pledge.get("target_price_per_kg"))),
            ],
            styles,
            palette,
        ),
        Spacer(1, 7 * mm),
        Paragraph("Buyer rules", styles["SectionHeading"]),
    ]

    required_lines = criterion_lines(buyer_pledge["criteria"]["required_inputs"]) or ["None recorded"]
    blocked_lines = criterion_lines(buyer_pledge["criteria"]["blocked_inputs"]) or ["None recorded"]
    story.extend(
        [
            Paragraph(f"<b>Required</b><br/>{'<br/>'.join(required_lines)}", styles["Body"]),
            Paragraph(f"<b>Blocked</b><br/>{'<br/>'.join(blocked_lines)}", styles["Body"]),
            Spacer(1, 4 * mm),
            Paragraph("Batch composition", styles["SectionHeading"]),
        ]
    )

    if allocations:
        story.append(
            simple_table(
                ["Farm", "Offer", "Contribution", "Available from", "Status"],
                [
                    [
                        f"{row['farm_name']}<br/>{row['county'] or 'County n/a'}, {row['region'] or 'Region n/a'}",
                        f"#{row['farmer_pledge_id']} · {row['farmer_crop_type']}",
                        quantity_text(row["allocated_quantity_kg"]),
                        format_date(row.get("available_from_date")),
                        str(row.get("farmer_pledge_status") or "Unknown").title(),
                    ]
                    for row in allocations
                ],
                styles=styles,
                palette=palette,
                col_widths=[54 * mm, 40 * mm, 28 * mm, 28 * mm, 28 * mm],
            )
        )
    else:
        story.append(Paragraph("No confirmed farm contributions have been recorded for this pledge yet.", styles["Body"]))

    story.extend([Spacer(1, 6 * mm), Paragraph("Batch input logs", styles["SectionHeading"])])
    if allocations:
        log_rows: list[list[str]] = []
        for row in allocations:
            if row["logs"]:
                for log in row["logs"]:
                    log_rows.append(
                        [
                            row["farm_name"],
                            f"#{row['farmer_pledge_id']} · {row['farmer_crop_type']}",
                            format_date(log.get("log_date")),
                            criterion_label(log),
                            f"{log.get('quantity')} {log.get('unit')}",
                            str(log.get("application_method") or "Not recorded"),
                            str(log.get("notes") or "No note"),
                        ]
                    )
            else:
                log_rows.append(
                    [
                        row["farm_name"],
                        f"#{row['farmer_pledge_id']} · {row['farmer_crop_type']}",
                        "Not recorded",
                        "No crop input logs",
                        "n/a",
                        "n/a",
                        "No note",
                    ]
                )
        story.append(
            simple_table(
                ["Farm", "Offer", "Date", "Input", "Qty", "Method", "Notes"],
                log_rows,
                styles=styles,
                palette=palette,
                col_widths=[24 * mm, 22 * mm, 16 * mm, 38 * mm, 12 * mm, 20 * mm, 42 * mm],
            )
        )
    else:
        story.append(Paragraph("Input logs will appear once farm contributions have been confirmed.", styles["Body"]))
    return story


def build_farmer_report_story(context: dict[str, Any], styles: StyleSheet1, palette: dict[str, colors.Color]) -> list[Any]:
    """Return the farmer-oriented report story."""
    buyer_pledge = context["buyer_pledge"]
    farms = context["farms"]
    story: list[Any] = []
    if not farms:
        return [
            Paragraph("Farmer participation report", styles["ReportKicker"]),
            Paragraph(f"Pledge #{buyer_pledge['buyer_pledge_id']}", styles["Title"]),
            Paragraph("No participating farms have been confirmed for this buyer pledge yet.", styles["Body"]),
        ]

    for index, farm in enumerate(farms):
        if index:
            story.append(PageBreak())
        story.extend(
            [
                Paragraph("Farmer participation report", styles["ReportKicker"]),
                Paragraph(farm["farm_name"], styles["Title"]),
                Paragraph(
                    f"{farm['farmer_name']} · {farm.get('county') or 'County n/a'}, {farm.get('region') or 'Region n/a'} · linked to buyer pledge #{buyer_pledge['buyer_pledge_id']}",
                    styles["ReportSubhead"],
                ),
                stat_table(
                    [
                        ("Buyer", buyer_pledge["organisation_name"]),
                        ("Crop", buyer_pledge["crop_type"]),
                        ("Farm contribution", quantity_text(farm["total_allocated_kg"])),
                        ("Farm offers in batch", str(len(farm["allocations"]))),
                        ("Farm contact", farm.get("farm_email") or farm.get("farm_phone") or "Not recorded"),
                        ("Coordinates", f"{farm.get('latitude') or 'n/a'}, {farm.get('longitude') or 'n/a'}"),
                    ],
                    styles,
                    palette,
                ),
                Spacer(1, 6 * mm),
                Paragraph("Contribution detail", styles["SectionHeading"]),
                simple_table(
                    ["Offer", "Committed", "Offer status", "Recorded logs", "Confirmed"],
                    [
                        [
                            f"#{row['farmer_pledge_id']} · {row['farmer_crop_type']}",
                            quantity_text(row["allocated_quantity_kg"]),
                            str(row.get("farmer_pledge_status") or "Unknown").title(),
                            f"{len(row['logs'])} log(s)",
                            format_timestamp(row.get("allocation_created_at")),
                        ]
                        for row in farm["allocations"]
                    ],
                    styles=styles,
                    palette=palette,
                    col_widths=[40 * mm, 26 * mm, 30 * mm, 26 * mm, 48 * mm],
                ),
                Spacer(1, 5 * mm),
                Paragraph("Production records", styles["SectionHeading"]),
            ]
        )

        for row in farm["allocations"]:
            snapshot = row["rule_snapshot"]
            story.append(
                Paragraph(
                    f"<b>Offer #{row['farmer_pledge_id']}</b> · {quantity_text(row['allocated_quantity_kg'])} committed",
                    styles["Body"],
                )
            )
            if row["logs"]:
                story.append(
                    simple_table(
                        ["Log date", "Input", "Qty", "Notes"],
                        [
                            [
                                format_date(log.get("log_date")),
                                criterion_label(log),
                                f"{log.get('quantity')} {log.get('unit')}",
                                str(log.get("notes") or "No note"),
                            ]
                            for log in row["logs"][:5]
                        ],
                        styles=styles,
                        palette=palette,
                        col_widths=[24 * mm, 66 * mm, 24 * mm, 56 * mm],
                    )
                )
            else:
                story.append(Paragraph("No crop input logs were recorded for this offer.", styles["Body"]))

            story.append(
                Paragraph(
                    f"<b>Required matched</b>: {', '.join(snapshot['matched_required']) or 'None'}<br/>"
                    f"<b>Required still missing</b>: {', '.join(snapshot['missing_required']) or 'None'}<br/>"
                    f"<b>Blocked matches</b>: {', '.join(snapshot['blocked_matches']) or 'None'}",
                    styles["Body"],
                )
            )
            story.append(Spacer(1, 4 * mm))

    return story


def render_pdf(story: list[Any], *, title: str) -> bytes:
    """Render a platypus story into PDF bytes."""
    brand = load_brand_manifest()
    styles, palette = build_styles(brand)
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        title=title,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=22 * mm,
        bottomMargin=18 * mm,
    )
    doc.build(
        story,
        onFirstPage=lambda canvas, document: report_header_footer(canvas, document, brand, palette),
        onLaterPages=lambda canvas, document: report_header_footer(canvas, document, brand, palette),
    )
    return buffer.getvalue()


def build_buyer_summary_pdf(buyer_pledge_id: int) -> bytes:
    """Generate the buyer-oriented PDF report for one buyer pledge."""
    brand = load_brand_manifest()
    styles, palette = build_styles(brand)
    context = fetch_batch_report_context(buyer_pledge_id)
    story = build_buyer_report_story(context, styles, palette)
    return render_pdf(story, title=f"{brand['name']} Buyer Batch Report")


def build_farmer_summary_pdf(buyer_pledge_id: int) -> bytes:
    """Generate the farmer-oriented multi-page PDF report for one buyer pledge."""
    brand = load_brand_manifest()
    styles, palette = build_styles(brand)
    context = fetch_batch_report_context(buyer_pledge_id)
    story = build_farmer_report_story(context, styles, palette)
    return render_pdf(story, title=f"{brand['name']} Farmer Participation Report")
