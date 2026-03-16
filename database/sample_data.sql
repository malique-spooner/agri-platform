DELETE FROM farm_input_logs;
DELETE FROM pledge_allocations;
DELETE FROM farmer_pledges;
DELETE FROM buyer_pledges;
DELETE FROM farmer_accounts;
DELETE FROM buyer_accounts;

INSERT INTO buyer_accounts (
    buyer_account_id,
    organisation_name,
    contact_name,
    email,
    phone
) VALUES (
    1,
    'Green Basket Co-op',
    'Maya Wilson',
    'maya@greenbasket.example',
    '555-0100'
);

INSERT INTO buyer_pledges (
    buyer_pledge_id,
    buyer_account_id,
    crop_type,
    quantity_kg,
    target_price_per_kg,
    needed_by_date,
    pledge_status,
    notes
) VALUES
    (1, 1, 'Tomatoes', 1200, 1.90, '2026-06-01', 'open', 'Weekly supply needed for school meal partners.'),
    (2, 1, 'Beans', 800, 2.40, '2026-07-15', 'open', 'Priority for farmers using low-input production methods.');

INSERT INTO farmer_accounts (
    farmer_account_id,
    farm_name,
    farmer_name,
    county,
    region,
    email,
    phone,
    total_hectares
) VALUES
    (1, 'Sunrise Fields', 'Amina Njoroge', 'Nakuru', 'Rift Valley', 'amina@sunrise.example', '555-0201', 12.5),
    (2, 'Riverbend Farm', 'David Otieno', 'Kiambu', 'Central', 'david@riverbend.example', '555-0202', 8.0),
    (3, 'Highland Greens', 'Lilian Mwangi', 'Meru', 'Eastern', 'lilian@highland.example', '555-0203', 15.2),
    (4, 'Valley Harvest', 'Peter Kimani', 'Machakos', 'Eastern', 'peter@valleyharvest.example', '555-0204', 10.7);

INSERT INTO farmer_pledges (
    farmer_pledge_id,
    farmer_account_id,
    crop_type,
    quantity_kg,
    asking_price_per_kg,
    available_from_date,
    pledge_status,
    notes
) VALUES
    (1, 1, 'Tomatoes', 500, 1.85, '2026-05-20', 'available', 'Open-field tomatoes from drip irrigation block.'),
    (2, 2, 'Tomatoes', 450, 1.95, '2026-05-25', 'available', 'Mixed variety harvest.'),
    (3, 3, 'Beans', 300, 2.30, '2026-06-30', 'available', 'Dry beans suitable for bulk packaging.'),
    (4, 4, 'Beans', 350, 2.45, '2026-07-05', 'available', 'Second planting expected to improve total volume.'),
    (5, 3, 'Tomatoes', 200, 1.80, '2026-05-28', 'available', 'Protected cultivation tunnel harvest.');

INSERT INTO pledge_allocations (
    allocation_id,
    buyer_pledge_id,
    farmer_pledge_id,
    allocated_quantity_kg,
    allocation_status
) VALUES
    (1, 1, 1, 400, 'proposed'),
    (2, 1, 2, 350, 'proposed'),
    (3, 2, 3, 250, 'proposed');

INSERT INTO farm_input_logs (
    input_log_id,
    farmer_account_id,
    farmer_pledge_id,
    input_type,
    quantity,
    unit,
    log_date,
    notes
) VALUES
    (1, 1, 1, 'Organic fertiliser', 120, 'kg', '2026-03-01', 'Applied before flowering stage.'),
    (2, 2, 2, 'Drip irrigation water', 18, 'm3', '2026-03-05', 'Recorded for weekly water tracking.'),
    (3, 3, 3, 'Compost', 90, 'kg', '2026-03-08', 'Applied to bean plot.'),
    (4, 4, NULL, 'Certified seed', 25, 'kg', '2026-02-20', 'Seed purchased for next planting cycle.');
