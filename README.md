# TRN Farmer Trace & Collective Trade System

Version 0 prototype for the TRN NGO agricultural aggregation model. Supports smallholder farmer registration, coffee lot assembly, and traceability report generation for EU-facing exporters in Uganda and Kenya.

## Current Scope

The current prototype supports the workflow for:

- registering coffee farmers from `/farmers/register`
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

## Share This Project

The easiest way to share this project is to send the GitHub repository link:

- [github.com/malique-spooner/trn-farmer-trace](https://github.com/malique-spooner/trn-farmer-trace)

Anyone reviewing the project can run it locally with these steps:

```bash
git clone https://github.com/malique-spooner/trn-farmer-trace.git
cd trn-farmer-trace
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
python database/setup_database.py
python database/generate_data.py
python app.py
```

Then open:

- [http://127.0.0.1:5000/](http://127.0.0.1:5000/)

That route opens the Export Lots queue, which is the main homepage for the prototype.

If a reviewer wants to reset the demo data back to the seeded state, they can either:

- use the `Reset database` action on `/settings`
- or rerun `python database/generate_data.py`

If a reviewer only wants to inspect the stored data without running the UI, they can open:

- `database/app_data.db`

with any SQLite browser such as DB Browser for SQLite.

## Installation

Create and activate a virtual environment, then install dependencies:

```bash
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Alternatively, install the project with dev tools using the pyproject.toml:

```bash
pip install -e ".[dev]"
```

## Database Setup

Create or update the SQLite schema:

```bash
python database/setup_database.py
```

Generate the seeded demo dataset:

```bash
python database/generate_data.py
```

The default generator produces:

- 20 buyer pledges
- farms only in Uganda and Kenya
- realistic recent dates relative to the current date
- standardized crop input records linked to the input catalog

## Running the App

Run the Flask application:

```bash
python app.py
```

Or with the Flask CLI (after activating the venv):

```bash
flask run
```

For deployment, use a WSGI server such as `gunicorn` with the included `Procfile`.

The main working pages are:

- `/farmers/register` farmer registration
- `/export-lots/new` create export lot form
- `/buyer-pledges` buyer-demand queue and homepage
- `/buyer-pledges/<pledge_id>/allocation` batch builder
- `/farms` registered farms directory
- `/farms/<farm_id>` farm profile
- `/farms/<farm_id>/pledges/<pledge_id>` crop-offer detail
- `/settings` input catalog management and demo reset

## Testing

Run the tests:

```bash
pytest -q
```

Run coverage-aware tests:

```bash
pytest --cov
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
- `farm_input_logs` and related crop input record helpers

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
