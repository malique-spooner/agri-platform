# Agri Platform

Version 0 prototype for coordinating agricultural supply pledges between buyers and farmers.

## Current Scope

The current prototype supports the aggregator workflow for:

- reviewing buyer pledges from the homepage
- browsing the farm directory
- drilling into farm profiles and crop-offer detail pages
- staging and submitting supply allocations against buyer demand
- exporting buyer-batch and farmer-participation PDF reports from the allocation view

## Setup

Create the SQLite database:

```bash
./venv/bin/python database/setup_database.py
```

Generate a synthetic dataset:

```bash
./venv/bin/python database/generate_data.py
```

Run the Flask application:

```bash
./venv/bin/python app.py
```

Run the tests:

```bash
./venv/bin/python -m pytest -q
```

## Project Structure

Key folders:

- `database/` schema setup, synthetic data generation, and the SQLite database file
- `logic/` allocation logic, database helpers, and shared logging setup
- `pages/` Flask templates
- `static/` CSS and any future client-side assets
- `tests/` route, logic, and database coverage
- `docs/` project documentation, including the development log

## Logging

The project uses Python's standard `logging` library for runtime logging.

- Development documentation is kept in `docs/dev_log.txt`.
- Runtime application logs are written to one file: `logs/app.log`.
- Rotated sibling files such as `app.log.1` are no longer part of the logging setup.
- If older rotated files exist from previous runs, they should be merged back into `app.log` and removed.

## Main Routes

- `/buyer-pledges` aggregator homepage and demand queue
- `/buyer-pledges/<pledge_id>/allocation` allocation builder
- `/farms` farm directory
- `/farms/<farm_id>` farm profile
- `/farms/<farm_id>/pledges/<pledge_id>` crop-offer detail with input history
- `/settings` input catalog management and demo-database reset
