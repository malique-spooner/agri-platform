# Agri Platform

Version 0 prototype for coordinating agricultural supply pledges between buyers and farmers.

## Current Scope

The current prototype supports the aggregator workflow for:

- reviewing buyer pledges from the homepage
- browsing the farm directory
- drilling into farm profiles and crop-offer detail pages
- staging and submitting supply allocations against buyer demand
- exporting buyer-batch and farmer-participation PDF reports from the allocation view
- managing a standardized input catalog from the settings page
- resetting the demo database back to a seeded operating state

## Technology Stack

- Python 3.11+
- Flask
- SQLite
- ReportLab
- Pytest

## Installation

Create and activate a virtual environment, then install the project with dev tools:

```bash
./venv/bin/pip install -e ".[dev]"
```

## Database Setup

Create or update the SQLite schema:

```bash
./venv/bin/python database/setup_database.py
```

Generate the seeded demo dataset:

```bash
./venv/bin/python database/generate_data.py
```

The default generator produces:

- 20 buyer pledges
- farms only in Uganda, Kenya, and Zambia
- realistic recent dates relative to the current date
- standardized crop input logs linked to the input catalog

## Running the App

Run the Flask application:

```bash
./venv/bin/python app.py
```

The main working pages are:

- `/buyer-pledges` buyer-demand queue and homepage
- `/buyer-pledges/<pledge_id>/allocation` batch builder
- `/farms` farm directory
- `/farms/<farm_id>` farm profile
- `/farms/<farm_id>/pledges/<pledge_id>` crop-offer detail
- `/settings` input catalog management and demo reset

## Testing

Run the tests:

```bash
./venv/bin/python -m pytest -q
```

Run coverage-aware tests:

```bash
./venv/bin/python -m pytest --cov
```

Run lint checks:

```bash
./venv/bin/python -m ruff check .
```

Format imports and style issues automatically where safe:

```bash
./venv/bin/python -m ruff check . --fix
```

## Project Structure

Key folders:

- `database/` schema setup, synthetic data generation, and the SQLite database file
- `logic/` allocation logic, database helpers, and shared logging setup
- `pages/` Flask templates
- `static/` CSS and any future client-side assets
- `tests/` route, logic, and database coverage
- `docs/` project documentation, including the development log

## Data Model Summary

The prototype currently uses seven tables:

- `buyer_accounts`
- `buyer_pledges`
- `farmer_accounts`
- `farmer_pledges`
- `pledge_allocations`
- `input_catalog`
- `farm_input_logs`

Buyer demand is created by buyer accounts, farmer supply is created by farmer accounts, and the allocation table links a buyer pledge to one or more farm offers. Input logs and the input catalog support traceability and buyer-rule matching.

## Logging

The project uses Python's standard `logging` library for runtime logging.

- Development documentation is kept in `docs/dev_log.txt`.
- Runtime application logs are written to one file: `logs/app.log`.
- Rotated sibling files such as `app.log.1` are no longer part of the logging setup.
- If older rotated files exist from previous runs, they should be merged back into `app.log` and removed.

## PDF Reports

Completed batches can export two report perspectives from the allocation page:

- buyer batch summary PDF
- farmer participation PDF

Exports stay disabled until the buyer pledge is fully fulfilled.

## Settings

The settings page provides:

- standardized input catalog management
- safe removal or deactivation of catalog entries
- demo database reset

The reset action rebuilds the seeded local SQLite database used by the app.

## Documentation

Supporting reference documents are kept in `docs/`, including:

- `dev_log.txt`
- `brand_guidelines.txt`
- `test_inventory.txt`
- `database_schema_reference.txt`
