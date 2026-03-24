"""Generate deterministic synthetic data for the agricultural coordination platform."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import json
import logging
from pathlib import Path
import random
import sqlite3
import sys


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATABASE_PATH = PROJECT_ROOT / "database" / "app_data.db"
sys.path.insert(0, str(PROJECT_ROOT))

from logic.logging_config import configure_logging
from database.setup_database import initialise_database


logger = logging.getLogger(__name__)

CROPS = [
    "Tomatoes",
    "Beans",
    "Maize",
    "Onions",
    "Potatoes",
    "Kale",
    "Cabbage",
    "Carrots",
    "Spinach",
    "Peppers",
]
BUYER_CROP_WEIGHTS = [18, 17, 15, 13, 10, 7, 6, 6, 4, 4]
FARMER_CROP_WEIGHTS = [13, 12, 10, 9, 15, 14, 11, 7, 5, 4]
REGIONS = {
    "Kenya": ["Nakuru", "Kiambu", "Meru", "Machakos"],
    "Tanzania": ["Arusha", "Morogoro", "Mbeya", "Dodoma"],
    "Uganda": ["Wakiso", "Mbarara", "Gulu", "Mbale"],
    "Rwanda": ["Eastern Province", "Northern Province", "Southern Province"],
    "Malawi": ["Lilongwe", "Mzuzu", "Blantyre", "Zomba"],
    "Zambia": ["Lusaka", "Central", "Copperbelt", "Eastern"],
    "Zimbabwe": ["Mashonaland East", "Midlands", "Manicaland", "Masvingo"],
}
REGION_COORDINATE_RANGES = {
    "Kenya": {"lat": (-4.75, 4.62), "lon": (33.91, 41.90)},
    "Tanzania": {"lat": (-11.75, -0.98), "lon": (29.34, 40.44)},
    "Uganda": {"lat": (-1.48, 4.23), "lon": (29.57, 35.04)},
    "Rwanda": {"lat": (-2.84, -1.05), "lon": (28.86, 30.90)},
    "Malawi": {"lat": (-17.13, -9.37), "lon": (32.67, 35.92)},
    "Zambia": {"lat": (-18.08, -8.20), "lon": (21.99, 33.70)},
    "Zimbabwe": {"lat": (-22.43, -15.61), "lon": (25.24, 33.06)},
}
FIRST_NAMES = [
    "Amina",
    "David",
    "Lilian",
    "Peter",
    "Grace",
    "Samuel",
    "Faith",
    "Brian",
    "Mercy",
    "Daniel",
    "Maya",
    "Naomi",
    "Kevin",
    "Esther",
    "James",
    "Ruth",
]
LAST_NAMES = [
    "Njoroge",
    "Otieno",
    "Mwangi",
    "Kimani",
    "Wambui",
    "Kamau",
    "Achieng",
    "Kiptoo",
    "Mutua",
    "Maina",
    "Ouma",
    "Chebet",
]
BUYER_PREFIXES = [
    "Green",
    "Harvest",
    "Fresh",
    "River",
    "Market",
    "Community",
    "Metro",
    "School",
    "Urban",
    "Regional",
]
BUYER_SUFFIXES = [
    "Basket",
    "Foods",
    "Supply",
    "Collective",
    "Hub",
    "Markets",
    "Stores",
    "Kitchen",
    "Distributors",
    "Partnership",
]
BUYER_TYPES = ["Co-op", "Ltd", "Network", "Group", "Association"]
FARM_PREFIXES = [
    "Sunrise",
    "Riverbend",
    "Highland",
    "Valley",
    "Greenfield",
    "Maple",
    "Red Soil",
    "Blue Sky",
    "North Ridge",
    "Golden Acre",
]
FARM_SUFFIXES = ["Farm", "Fields", "Holdings", "Acres", "Gardens"]
INPUT_CATALOG = [
    {
        "input_type": "Pesticide",
        "product_name": "Azadirachtin extract",
        "brand_name": "EcoNeem",
        "application_method": "Foliar spray",
        "unit": "L",
        "quantity_range": (1, 18),
    },
    {
        "input_type": "Pesticide",
        "product_name": "Pyrethrin spray",
        "brand_name": "CropShield",
        "application_method": "Knapsack spray",
        "unit": "L",
        "quantity_range": (1, 14),
    },
    {
        "input_type": "Fertiliser",
        "product_name": "Organic compost",
        "brand_name": "SoilRich",
        "application_method": "Soil incorporation",
        "unit": "kg",
        "quantity_range": (80, 650),
    },
    {
        "input_type": "Fertiliser",
        "product_name": "NPK 17-17-17",
        "brand_name": "GreenGrow",
        "application_method": "Side dressing",
        "unit": "kg",
        "quantity_range": (40, 300),
    },
    {
        "input_type": "Seed treatment",
        "product_name": "Certified seed dressing",
        "brand_name": "SeedSure",
        "application_method": "Pre-plant seed coat",
        "unit": "kg",
        "quantity_range": (5, 80),
    },
    {
        "input_type": "Irrigation",
        "product_name": "Drip irrigation cycle",
        "brand_name": None,
        "application_method": "Drip line",
        "unit": "m3",
        "quantity_range": (6, 180),
    },
    {
        "input_type": "Mulch",
        "product_name": "Organic mulch cover",
        "brand_name": None,
        "application_method": "Bed coverage",
        "unit": "rolls",
        "quantity_range": (1, 25),
    },
    {
        "input_type": "Soil amendment",
        "product_name": "Agricultural lime",
        "brand_name": "FieldBalance",
        "application_method": "Broadcast application",
        "unit": "kg",
        "quantity_range": (50, 500),
    },
]


def parse_args() -> argparse.Namespace:
    """Parse generation parameters."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--buyers", type=int, default=120)
    parser.add_argument("--farmers", type=int, default=180)
    parser.add_argument("--max-buyer-pledges", type=int, default=5)
    parser.add_argument("--max-farmer-pledges", type=int, default=6)
    parser.add_argument("--max-input-logs", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260324)
    parser.add_argument("--database-path", type=Path, default=DATABASE_PATH)
    return parser.parse_args()


def iso_timestamp(value: datetime) -> str:
    """Return a SQLite-friendly timestamp."""
    return value.replace(microsecond=0).isoformat(sep=" ")


def iso_date(value: datetime) -> str:
    """Return an ISO date string."""
    return value.date().isoformat()


def random_datetime(rng: random.Random, now: datetime, max_days_back: int = 540) -> datetime:
    """Return a realistic timestamp in the recent past."""
    days_back = rng.randint(0, max_days_back)
    seconds_back = rng.randint(0, 24 * 60 * 60 - 1)
    return now - timedelta(days=days_back, seconds=seconds_back)


def maybe_none(rng: random.Random, value, probability: float):
    """Return None with the requested probability."""
    return None if rng.random() < probability else value


def random_name(rng: random.Random) -> str:
    """Return a realistic personal name."""
    return f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}"


def build_buyer_name(rng: random.Random, index: int) -> str:
    """Return a deterministic organisation name."""
    return (
        f"{rng.choice(BUYER_PREFIXES)} {rng.choice(BUYER_SUFFIXES)} "
        f"{rng.choice(BUYER_TYPES)} {index + 1}"
    )


def build_farm_name(rng: random.Random) -> str:
    """Return a farm name."""
    return f"{rng.choice(FARM_PREFIXES)} {rng.choice(FARM_SUFFIXES)}"


def random_phone(rng: random.Random) -> str:
    """Return a synthetic phone number."""
    return f"555-{rng.randint(1000, 9999)}"


def region_bounds(region: str) -> dict[str, tuple[float, float]]:
    """Return latitude/longitude bounds for a supported country."""
    return REGION_COORDINATE_RANGES[region]


def random_coordinates_for_region(rng: random.Random, region: str) -> tuple[float, float]:
    """Return plausible coordinates for a farm in the selected region."""
    bounds = region_bounds(region)
    latitude = round(rng.uniform(*bounds["lat"]), 5)
    longitude = round(rng.uniform(*bounds["lon"]), 5)
    return latitude, longitude


def choose_crop(rng: random.Random, weights: list[int]) -> str:
    """Choose a crop using deterministic weighted randomness."""
    return rng.choices(CROPS, weights=weights, k=1)[0]


def choose_input_record(rng: random.Random) -> dict[str, object]:
    """Return a structured input record for log generation."""
    return rng.choice(INPUT_CATALOG)


def choose_pledge_count(
    rng: random.Random,
    max_count: int,
    zero_indexes: set[int],
    index: int,
) -> int:
    """Choose how many pledges to create for an actor."""
    if max_count <= 0 or index in zero_indexes:
        return 0
    if max_count == 1:
        return 1
    return rng.randint(1, max_count)


def clear_existing_data(connection: sqlite3.Connection) -> None:
    """Remove existing data while preserving the schema."""
    for table_name in (
        "farm_input_logs",
        "pledge_allocations",
        "farmer_pledges",
        "buyer_pledges",
        "farmer_accounts",
        "buyer_accounts",
    ):
        connection.execute(f"DELETE FROM {table_name}")
    connection.commit()


def insert_buyer_accounts(
    connection: sqlite3.Connection,
    rng: random.Random,
    buyer_count: int,
    now: datetime,
) -> list[dict[str, object]]:
    """Insert buyer accounts and return the inserted records."""
    buyers: list[dict[str, object]] = []
    for index in range(buyer_count):
        created_at = random_datetime(rng, now)
        contact_name = random_name(rng)
        organisation_name = build_buyer_name(rng, index)
        email_slug = organisation_name.lower().replace(" ", "_")
        email = f"{email_slug}@buyers.example"
        phone = maybe_none(rng, random_phone(rng), 0.25)
        cursor = connection.execute(
            """
            INSERT INTO buyer_accounts (
                organisation_name,
                contact_name,
                email,
                phone,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                organisation_name,
                contact_name,
                email,
                phone,
                iso_timestamp(created_at),
            ),
        )
        buyers.append(
            {
                "buyer_account_id": cursor.lastrowid,
                "created_at": created_at,
            }
        )
    return buyers


def insert_farmer_accounts(
    connection: sqlite3.Connection,
    rng: random.Random,
    farmer_count: int,
    now: datetime,
) -> list[dict[str, object]]:
    """Insert farmer accounts and return the inserted records."""
    farmers: list[dict[str, object]] = []
    region_names = sorted(REGIONS)
    for _ in range(farmer_count):
        created_at = random_datetime(rng, now)
        farmer_name = random_name(rng)
        farm_name = build_farm_name(rng)
        region = rng.choice(region_names)
        county = rng.choice(REGIONS[region])
        latitude, longitude = random_coordinates_for_region(rng, region)
        email_name = farmer_name.lower().replace(" ", ".")
        email = maybe_none(rng, f"{email_name}@farmers.example", 0.35)
        phone = maybe_none(rng, random_phone(rng), 0.15)
        total_hectares = round(rng.uniform(2.5, 120.0), 1)
        cursor = connection.execute(
            """
            INSERT INTO farmer_accounts (
                farm_name,
                farmer_name,
                county,
                region,
                latitude,
                longitude,
                email,
                phone,
                total_hectares,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                farm_name,
                farmer_name,
                county,
                region,
                latitude,
                longitude,
                email,
                phone,
                total_hectares,
                iso_timestamp(created_at),
            ),
        )
        farmers.append(
            {
                "farmer_account_id": cursor.lastrowid,
                "created_at": created_at,
            }
        )
    return farmers


def insert_buyer_pledges(
    connection: sqlite3.Connection,
    rng: random.Random,
    buyers: list[dict[str, object]],
    max_pledges: int,
) -> list[dict[str, object]]:
    """Insert buyer pledges with realistic demand variation."""
    zero_indexes = set(rng.sample(range(len(buyers)), k=min(max(1, len(buyers) // 10), len(buyers))))
    pledges: list[dict[str, object]] = []
    for index, buyer in enumerate(buyers):
        pledge_count = choose_pledge_count(rng, max_pledges, zero_indexes, index)
        for _ in range(pledge_count):
            created_at = buyer["created_at"] + timedelta(days=rng.randint(0, 30))
            crop_type = choose_crop(rng, BUYER_CROP_WEIGHTS)
            quantity_kg = rng.randint(250, 5000)
            target_price_per_kg = maybe_none(rng, round(rng.uniform(0.8, 4.5), 2), 0.3)
            needed_by_date = maybe_none(
                rng,
                iso_date(created_at + timedelta(days=rng.randint(14, 180))),
                0.12,
            )
            notes_payload = {
                "priority": rng.choice(["standard", "nutrition-programme", "bulk-distribution"]),
                "organic_preference": rng.choice([True, False]),
                "delivery_window_days": rng.randint(3, 21),
            }
            notes = json.dumps(notes_payload, sort_keys=True)
            cursor = connection.execute(
                """
                INSERT INTO buyer_pledges (
                    buyer_account_id,
                    crop_type,
                    quantity_kg,
                    target_price_per_kg,
                    needed_by_date,
                    pledge_status,
                    notes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    buyer["buyer_account_id"],
                    crop_type,
                    quantity_kg,
                    target_price_per_kg,
                    needed_by_date,
                    "open",
                    notes,
                    iso_timestamp(created_at),
                ),
            )
            pledges.append(
                {
                    "buyer_pledge_id": cursor.lastrowid,
                    "buyer_account_id": buyer["buyer_account_id"],
                    "crop_type": crop_type,
                    "quantity_kg": quantity_kg,
                    "created_at": created_at,
                }
            )
    return pledges


def insert_farmer_pledges(
    connection: sqlite3.Connection,
    rng: random.Random,
    farmers: list[dict[str, object]],
    max_pledges: int,
) -> list[dict[str, object]]:
    """Insert farmer pledges with realistic supply variation."""
    zero_indexes = set(rng.sample(range(len(farmers)), k=min(max(1, len(farmers) // 8), len(farmers))))
    pledges: list[dict[str, object]] = []
    for index, farmer in enumerate(farmers):
        pledge_count = choose_pledge_count(rng, max_pledges, zero_indexes, index)
        for _ in range(pledge_count):
            created_at = farmer["created_at"] + timedelta(days=rng.randint(0, 40))
            crop_type = choose_crop(rng, FARMER_CROP_WEIGHTS)
            quantity_kg = rng.randint(180, 4200)
            asking_price_per_kg = maybe_none(rng, round(rng.uniform(0.7, 4.0), 2), 0.25)
            available_from_date = maybe_none(
                rng,
                iso_date(created_at + timedelta(days=rng.randint(7, 150))),
                0.18,
            )
            notes = maybe_none(
                rng,
                rng.choice(
                    [
                        "Drip-irrigated block.",
                        "Rain-fed production cycle.",
                        "Protected cultivation harvest.",
                        "Bulk delivery available.",
                    ]
                ),
                0.4,
            )
            cursor = connection.execute(
                """
                INSERT INTO farmer_pledges (
                    farmer_account_id,
                    crop_type,
                    quantity_kg,
                    asking_price_per_kg,
                    available_from_date,
                    pledge_status,
                    notes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    farmer["farmer_account_id"],
                    crop_type,
                    quantity_kg,
                    asking_price_per_kg,
                    available_from_date,
                    "available",
                    notes,
                    iso_timestamp(created_at),
                ),
            )
            pledges.append(
                {
                    "farmer_pledge_id": cursor.lastrowid,
                    "farmer_account_id": farmer["farmer_account_id"],
                    "crop_type": crop_type,
                    "quantity_kg": quantity_kg,
                    "created_at": created_at,
                }
            )
    return pledges


def build_allocation_target(
    rng: random.Random,
    demand_quantity: int,
    max_available: int,
    target_mode: str,
) -> int:
    """Choose a total allocation amount consistent with the desired scenario."""
    if max_available <= 0 or target_mode == "open":
        return 0
    if target_mode == "fulfilled" and max_available >= demand_quantity:
        return demand_quantity
    if target_mode == "partial":
        upper_bound = min(demand_quantity - 1, max_available)
        if upper_bound <= 0:
            return 0
        lower_bound = max(1, min(upper_bound, max(1, demand_quantity // 4)))
        return rng.randint(lower_bound, upper_bound)
    if max_available >= demand_quantity and rng.random() < 0.5:
        return demand_quantity
    return min(max_available, max(1, demand_quantity // 2))


def insert_allocations(
    connection: sqlite3.Connection,
    rng: random.Random,
    buyer_pledges: list[dict[str, object]],
    farmer_pledges: list[dict[str, object]],
) -> None:
    """Allocate supply to demand while preserving quantity constraints."""
    farmer_by_crop: dict[str, list[dict[str, object]]] = {}
    remaining_supply: dict[int, int] = {}
    buyer_allocated: dict[int, int] = {int(pledge["buyer_pledge_id"]): 0 for pledge in buyer_pledges}
    farmer_allocated: dict[int, int] = {int(pledge["farmer_pledge_id"]): 0 for pledge in farmer_pledges}

    for pledge in farmer_pledges:
        farmer_by_crop.setdefault(str(pledge["crop_type"]), []).append(pledge)
        remaining_supply[int(pledge["farmer_pledge_id"])] = int(pledge["quantity_kg"])

    mode_cycle = ["open", "partial", "fulfilled"]
    for index, buyer_pledge in enumerate(sorted(buyer_pledges, key=lambda item: int(item["buyer_pledge_id"]))):
        crop_type = str(buyer_pledge["crop_type"])
        demand_quantity = int(buyer_pledge["quantity_kg"])
        candidate_pledges = [
            pledge
            for pledge in farmer_by_crop.get(crop_type, [])
            if remaining_supply[int(pledge["farmer_pledge_id"])] > 0
        ]
        rng.shuffle(candidate_pledges)
        max_available = sum(remaining_supply[int(pledge["farmer_pledge_id"])] for pledge in candidate_pledges)
        target_total = build_allocation_target(rng, demand_quantity, max_available, mode_cycle[index % len(mode_cycle)])
        remaining_target = target_total

        while remaining_target > 0 and candidate_pledges:
            farmer_pledge = candidate_pledges.pop()
            farmer_pledge_id = int(farmer_pledge["farmer_pledge_id"])
            available_quantity = remaining_supply[farmer_pledge_id]
            max_chunk = min(available_quantity, remaining_target)
            allocation_quantity = max_chunk if not candidate_pledges else rng.randint(1, max_chunk)
            allocation_created_at = max(
                datetime.fromisoformat(str(buyer_pledge["created_at"])),
                datetime.fromisoformat(str(farmer_pledge["created_at"])),
            ) + timedelta(days=rng.randint(0, 45))
            connection.execute(
                """
                INSERT INTO pledge_allocations (
                    buyer_pledge_id,
                    farmer_pledge_id,
                    allocated_quantity_kg,
                    allocation_status,
                    created_at
                ) VALUES (?, ?, ?, ?, ?)
                """,
                (
                    buyer_pledge["buyer_pledge_id"],
                    farmer_pledge_id,
                    allocation_quantity,
                    rng.choice(["proposed", "confirmed"]),
                    iso_timestamp(allocation_created_at),
                ),
            )
            remaining_supply[farmer_pledge_id] -= allocation_quantity
            remaining_target -= allocation_quantity
            buyer_allocated[int(buyer_pledge["buyer_pledge_id"])] += allocation_quantity
            farmer_allocated[farmer_pledge_id] += allocation_quantity

            if remaining_supply[farmer_pledge_id] > 0:
                candidate_pledges.append(farmer_pledge)

    for pledge in buyer_pledges:
        buyer_pledge_id = int(pledge["buyer_pledge_id"])
        allocated_quantity = buyer_allocated[buyer_pledge_id]
        quantity_kg = int(pledge["quantity_kg"])
        if allocated_quantity == 0:
            status = "open"
        elif allocated_quantity >= quantity_kg:
            status = "fulfilled"
        else:
            status = "partial"
        connection.execute(
            "UPDATE buyer_pledges SET pledge_status = ? WHERE buyer_pledge_id = ?",
            (status, buyer_pledge_id),
        )

    for pledge in farmer_pledges:
        farmer_pledge_id = int(pledge["farmer_pledge_id"])
        allocated_quantity = farmer_allocated[farmer_pledge_id]
        quantity_kg = int(pledge["quantity_kg"])
        if allocated_quantity == 0:
            status = "available"
        elif allocated_quantity >= quantity_kg:
            status = "allocated"
        else:
            status = "partial"
        connection.execute(
            "UPDATE farmer_pledges SET pledge_status = ? WHERE farmer_pledge_id = ?",
            (status, farmer_pledge_id),
        )


def insert_farm_input_logs(
    connection: sqlite3.Connection,
    rng: random.Random,
    farmers: list[dict[str, object]],
    farmer_pledges: list[dict[str, object]],
    max_input_logs: int,
    now: datetime,
) -> None:
    """Insert dense crop-history logs while preserving some empty histories."""
    pledges_by_farmer: dict[int, list[dict[str, object]]] = {}
    for pledge in farmer_pledges:
        pledges_by_farmer.setdefault(int(pledge["farmer_account_id"]), []).append(pledge)

    for farmer in farmers:
        farmer_id = int(farmer["farmer_account_id"])
        if max_input_logs <= 0:
            continue
        farmer_pledge_options = pledges_by_farmer.get(farmer_id, [])
        if not farmer_pledge_options:
            continue

        if rng.random() >= 0.2:
            farm_log_count = rng.randint(1, max(2, max_input_logs // 3))
        else:
            farm_log_count = 0

        for _ in range(farm_log_count):
            input_record = choose_input_record(rng)
            unit = str(input_record["unit"])
            min_quantity, max_quantity = input_record["quantity_range"]
            log_base = random_datetime(rng, now, max_days_back=240)
            notes = maybe_none(
                rng,
                rng.choice(
                    [
                        "Applied as scheduled.",
                        "Recorded during field inspection.",
                        "Input tied to seasonal production cycle.",
                        "Tracked for cost and compliance review.",
                    ]
                ),
                0.45,
            )
            connection.execute(
                """
                INSERT INTO farm_input_logs (
                    farmer_account_id,
                    farmer_pledge_id,
                    input_type,
                    product_name,
                    brand_name,
                    application_method,
                    quantity,
                    unit,
                    log_date,
                    notes,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    farmer_id,
                    None,
                    input_record["input_type"],
                    input_record["product_name"],
                    input_record["brand_name"],
                    input_record["application_method"],
                    rng.randint(min_quantity, max_quantity),
                    unit,
                    iso_date(log_base),
                    notes,
                    iso_timestamp(log_base),
                ),
            )

        for pledge in farmer_pledge_options:
            if rng.random() < 0.15:
                continue

            pledge_created_at = datetime.fromisoformat(str(pledge["created_at"]))
            pledge_log_count = rng.randint(2, max_input_logs)
            for _ in range(pledge_log_count):
                input_record = choose_input_record(rng)
                unit = str(input_record["unit"])
                min_quantity, max_quantity = input_record["quantity_range"]
                days_forward = rng.randint(0, 120)
                log_base = pledge_created_at + timedelta(days=days_forward)
                if log_base > now:
                    log_base = now - timedelta(days=rng.randint(0, 10))
                notes = maybe_none(
                    rng,
                    rng.choice(
                        [
                            "Applied as scheduled for this crop block.",
                            "Recorded during agronomist field inspection.",
                            "Logged to support buyer compliance review.",
                            "Part of the standard production cycle for this offer.",
                            "Input timing tracked against harvest readiness.",
                        ]
                    ),
                    0.2,
                )
                connection.execute(
                    """
                    INSERT INTO farm_input_logs (
                        farmer_account_id,
                        farmer_pledge_id,
                        input_type,
                        product_name,
                        brand_name,
                        application_method,
                        quantity,
                        unit,
                        log_date,
                        notes,
                        created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        farmer_id,
                        pledge["farmer_pledge_id"],
                        input_record["input_type"],
                        input_record["product_name"],
                        input_record["brand_name"],
                        input_record["application_method"],
                        rng.randint(min_quantity, max_quantity),
                        unit,
                        iso_date(log_base),
                        notes,
                        iso_timestamp(log_base),
                    ),
                )


def validate_foreign_keys(connection: sqlite3.Connection) -> None:
    """Validate all foreign key relationships."""
    failures = connection.execute("PRAGMA foreign_key_check").fetchall()
    if failures:
        raise RuntimeError(f"Foreign key validation failed: {failures[:5]}")


def validate_quantities(connection: sqlite3.Connection) -> None:
    """Validate non-negative and positive quantity rules."""
    checks = {
        "buyer_pledges.quantity_kg": "SELECT COUNT(*) FROM buyer_pledges WHERE quantity_kg <= 0",
        "farmer_pledges.quantity_kg": "SELECT COUNT(*) FROM farmer_pledges WHERE quantity_kg <= 0",
        "pledge_allocations.allocated_quantity_kg": "SELECT COUNT(*) FROM pledge_allocations WHERE allocated_quantity_kg <= 0",
        "farm_input_logs.quantity": "SELECT COUNT(*) FROM farm_input_logs WHERE quantity <= 0",
        "farmer_accounts.total_hectares": "SELECT COUNT(*) FROM farmer_accounts WHERE total_hectares <= 0",
    }
    for label, query in checks.items():
        failing_count = connection.execute(query).fetchone()[0]
        if failing_count:
            raise RuntimeError(f"Quantity validation failed for {label}: {failing_count} invalid record(s)")


def validate_coordinates(connection: sqlite3.Connection) -> None:
    """Validate that farm coordinates and subregions match the configured African geography."""
    rows = connection.execute(
        "SELECT farmer_account_id, region, county, latitude, longitude FROM farmer_accounts"
    ).fetchall()
    for farmer_account_id, region, county, latitude, longitude in rows:
        if latitude is None or longitude is None:
            raise RuntimeError(
                f"Coordinate validation failed: farmer_account_id={farmer_account_id} is missing coordinates"
            )
        if region not in REGIONS:
            raise RuntimeError(
                f"Coordinate validation failed: farmer_account_id={farmer_account_id} has unsupported region '{region}'"
            )
        if county not in REGIONS[region]:
            raise RuntimeError(
                f"Coordinate validation failed: farmer_account_id={farmer_account_id} has county '{county}' outside region '{region}'"
            )

        bounds = region_bounds(region)
        if not (bounds["lat"][0] <= latitude <= bounds["lat"][1]):
            raise RuntimeError(
                f"Coordinate validation failed: farmer_account_id={farmer_account_id} latitude {latitude} outside {region} bounds"
            )
        if not (bounds["lon"][0] <= longitude <= bounds["lon"][1]):
            raise RuntimeError(
                f"Coordinate validation failed: farmer_account_id={farmer_account_id} longitude {longitude} outside {region} bounds"
            )


def validate_temporal_rules(connection: sqlite3.Connection) -> None:
    """Validate basic temporal consistency."""
    buyer_failures = connection.execute(
        """
        SELECT COUNT(*)
        FROM buyer_pledges
        WHERE needed_by_date IS NOT NULL
          AND date(needed_by_date) < date(created_at)
        """
    ).fetchone()[0]
    if buyer_failures:
        raise RuntimeError(f"Temporal validation failed for buyer pledges: {buyer_failures} invalid record(s)")

    farmer_failures = connection.execute(
        """
        SELECT COUNT(*)
        FROM farmer_pledges
        WHERE available_from_date IS NOT NULL
          AND date(available_from_date) < date(created_at)
        """
    ).fetchone()[0]
    if farmer_failures:
        raise RuntimeError(f"Temporal validation failed for farmer pledges: {farmer_failures} invalid record(s)")


def validate_input_log_structure(connection: sqlite3.Connection) -> None:
    """Validate that input logs carry future-proof classification details."""
    missing_product_names = connection.execute(
        "SELECT COUNT(*) FROM farm_input_logs WHERE product_name IS NULL OR TRIM(product_name) = ''"
    ).fetchone()[0]
    if missing_product_names:
        raise RuntimeError(
            f"Input-log validation failed: {missing_product_names} record(s) missing product names"
        )

    missing_methods = connection.execute(
        "SELECT COUNT(*) FROM farm_input_logs WHERE application_method IS NULL OR TRIM(application_method) = ''"
    ).fetchone()[0]
    if missing_methods:
        raise RuntimeError(
            f"Input-log validation failed: {missing_methods} record(s) missing application methods"
        )

    category_count = connection.execute(
        "SELECT COUNT(DISTINCT input_type) FROM farm_input_logs"
    ).fetchone()[0]
    if category_count < 4:
        raise RuntimeError(
            f"Input-log validation failed: expected at least 4 input categories, found {category_count}"
        )


def validate_allocations(connection: sqlite3.Connection) -> None:
    """Validate aggregate allocation rules for buyers and farmers."""
    buyer_rows = connection.execute(
        """
        SELECT
            bp.buyer_pledge_id,
            bp.quantity_kg,
            bp.pledge_status,
            COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity
        FROM buyer_pledges AS bp
        LEFT JOIN pledge_allocations AS pa
            ON bp.buyer_pledge_id = pa.buyer_pledge_id
        GROUP BY bp.buyer_pledge_id, bp.quantity_kg, bp.pledge_status
        """
    ).fetchall()
    for buyer_pledge_id, quantity_kg, pledge_status, allocated_quantity in buyer_rows:
        if allocated_quantity > quantity_kg:
            raise RuntimeError(
                f"Allocation exceeds buyer demand for buyer_pledge_id={buyer_pledge_id}: "
                f"{allocated_quantity} > {quantity_kg}"
            )
        expected_status = "open" if allocated_quantity == 0 else "fulfilled" if allocated_quantity == quantity_kg else "partial"
        if pledge_status != expected_status:
            raise RuntimeError(
                f"Buyer pledge status mismatch for buyer_pledge_id={buyer_pledge_id}: "
                f"expected {expected_status}, found {pledge_status}"
            )

    farmer_rows = connection.execute(
        """
        SELECT
            fp.farmer_pledge_id,
            fp.quantity_kg,
            fp.pledge_status,
            fp.farmer_account_id,
            COALESCE(SUM(pa.allocated_quantity_kg), 0) AS allocated_quantity
        FROM farmer_pledges AS fp
        LEFT JOIN pledge_allocations AS pa
            ON fp.farmer_pledge_id = pa.farmer_pledge_id
        GROUP BY fp.farmer_pledge_id, fp.quantity_kg, fp.pledge_status, fp.farmer_account_id
        """
    ).fetchall()
    for farmer_pledge_id, quantity_kg, pledge_status, _, allocated_quantity in farmer_rows:
        if allocated_quantity > quantity_kg:
            raise RuntimeError(
                f"Allocation exceeds farmer supply for farmer_pledge_id={farmer_pledge_id}: "
                f"{allocated_quantity} > {quantity_kg}"
            )
        expected_status = "available" if allocated_quantity == 0 else "allocated" if allocated_quantity == quantity_kg else "partial"
        if pledge_status != expected_status:
            raise RuntimeError(
                f"Farmer pledge status mismatch for farmer_pledge_id={farmer_pledge_id}: "
                f"expected {expected_status}, found {pledge_status}"
            )

    log_failures = connection.execute(
        """
        SELECT COUNT(*)
        FROM farm_input_logs AS fil
        INNER JOIN farmer_pledges AS fp
            ON fil.farmer_pledge_id = fp.farmer_pledge_id
        WHERE fil.farmer_pledge_id IS NOT NULL
          AND fil.farmer_account_id != fp.farmer_account_id
        """
    ).fetchone()[0]
    if log_failures:
        raise RuntimeError(f"Farm input log validation failed: {log_failures} mismatched farmer/pledge link(s)")


def validate_status_coverage(connection: sqlite3.Connection) -> None:
    """Ensure the generated dataset includes the required edge-case allocation states."""
    buyer_statuses = {
        row[0]: row[1]
        for row in connection.execute(
            "SELECT pledge_status, COUNT(*) FROM buyer_pledges GROUP BY pledge_status"
        ).fetchall()
    }
    for required_status in ("open", "partial", "fulfilled"):
        if buyer_statuses.get(required_status, 0) == 0:
            raise RuntimeError(f"Expected at least one buyer pledge with status '{required_status}'")


def table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    """Return row counts for all major tables."""
    tables = (
        "buyer_accounts",
        "buyer_pledges",
        "farmer_accounts",
        "farmer_pledges",
        "pledge_allocations",
        "farm_input_logs",
    )
    return {
        table_name: connection.execute(f"SELECT COUNT(*) FROM {table_name}").fetchone()[0]
        for table_name in tables
    }


def print_summary(connection: sqlite3.Connection) -> None:
    """Print a human-readable summary of generated data."""
    counts = table_counts(connection)
    print("Record counts:")
    for table_name, count in counts.items():
        print(f"- {table_name}: {count}")

    pledge_total = max(counts["buyer_pledges"], 1)
    status_rows = connection.execute(
        "SELECT pledge_status, COUNT(*) FROM buyer_pledges GROUP BY pledge_status ORDER BY pledge_status"
    ).fetchall()
    print("Allocation coverage:")
    for status, count in status_rows:
        percentage = (count / pledge_total) * 100
        print(f"- {status}: {count} ({percentage:.1f}%)")

    print("Detected anomalies:")
    print("- 0")


def generate_dataset(args: argparse.Namespace) -> None:
    """Create schema, populate synthetic data, validate it, and print a summary."""
    rng = random.Random(args.seed)
    now = datetime.now()

    initialise_database(args.database_path)
    with sqlite3.connect(args.database_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON;")
        clear_existing_data(connection)
        buyers = insert_buyer_accounts(connection, rng, args.buyers, now)
        farmers = insert_farmer_accounts(connection, rng, args.farmers, now)
        buyer_pledges = insert_buyer_pledges(connection, rng, buyers, args.max_buyer_pledges)
        farmer_pledges = insert_farmer_pledges(connection, rng, farmers, args.max_farmer_pledges)
        insert_allocations(connection, rng, buyer_pledges, farmer_pledges)
        insert_farm_input_logs(connection, rng, farmers, farmer_pledges, args.max_input_logs, now)
        connection.commit()

        validate_foreign_keys(connection)
        validate_quantities(connection)
        validate_coordinates(connection)
        validate_temporal_rules(connection)
        validate_input_log_structure(connection)
        validate_allocations(connection)
        validate_status_coverage(connection)
        print_summary(connection)


def main() -> None:
    """Parse arguments and run the generator."""
    args = parse_args()
    log_path = configure_logging()
    logger.info("Synthetic data generation started with seed=%s; logging to %s", args.seed, log_path)
    generate_dataset(args)
    logger.info("Synthetic data generation completed successfully")


if __name__ == "__main__":
    main()
