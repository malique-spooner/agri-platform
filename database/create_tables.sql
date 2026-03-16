PRAGMA foreign_keys = ON;

-- Stores buyer organisations that can create purchasing pledges.
CREATE TABLE IF NOT EXISTS buyer_accounts (
    buyer_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    organisation_name TEXT NOT NULL,
    contact_name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Stores crop demand posted by buyer organisations.
CREATE TABLE IF NOT EXISTS buyer_pledges (
    buyer_pledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_account_id INTEGER NOT NULL,
    crop_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    target_price_per_kg REAL,
    needed_by_date TEXT,
    pledge_status TEXT NOT NULL DEFAULT 'open',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_account_id) REFERENCES buyer_accounts (buyer_account_id)
);

-- Stores farmer account and farm profile details.
CREATE TABLE IF NOT EXISTS farmer_accounts (
    farmer_account_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farm_name TEXT NOT NULL,
    farmer_name TEXT NOT NULL,
    county TEXT,
    region TEXT,
    email TEXT,
    phone TEXT,
    total_hectares REAL,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Stores crop supply pledges offered by farmers.
CREATE TABLE IF NOT EXISTS farmer_pledges (
    farmer_pledge_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_account_id INTEGER NOT NULL,
    crop_type TEXT NOT NULL,
    quantity_kg REAL NOT NULL,
    asking_price_per_kg REAL,
    available_from_date TEXT,
    pledge_status TEXT NOT NULL DEFAULT 'available',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_account_id) REFERENCES farmer_accounts (farmer_account_id)
);

-- Links buyer pledges to one or more farmer pledges that help fulfill demand.
CREATE TABLE IF NOT EXISTS pledge_allocations (
    allocation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    buyer_pledge_id INTEGER NOT NULL,
    farmer_pledge_id INTEGER NOT NULL,
    allocated_quantity_kg REAL NOT NULL,
    allocation_status TEXT NOT NULL DEFAULT 'proposed',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (buyer_pledge_id) REFERENCES buyer_pledges (buyer_pledge_id),
    FOREIGN KEY (farmer_pledge_id) REFERENCES farmer_pledges (farmer_pledge_id)
);

-- Stores farm input usage records for farmers and, when relevant, a specific farmer pledge.
CREATE TABLE IF NOT EXISTS farm_input_logs (
    input_log_id INTEGER PRIMARY KEY AUTOINCREMENT,
    farmer_account_id INTEGER NOT NULL,
    farmer_pledge_id INTEGER,
    input_type TEXT NOT NULL,
    quantity REAL NOT NULL,
    unit TEXT NOT NULL,
    log_date TEXT NOT NULL,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (farmer_account_id) REFERENCES farmer_accounts (farmer_account_id),
    FOREIGN KEY (farmer_pledge_id) REFERENCES farmer_pledges (farmer_pledge_id)
);
