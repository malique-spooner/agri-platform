# Origin & Acre

A coffee supply-chain coordination prototype for farmer registration, buyer demand, farm offers and lot traceability. This is a student project and a product concept, not a production system or a service used by real farmers or buyers.

## Public demo

The project landing page is [Origin & Acre](https://maliquespooner.com/Origin-Acre/); its interactive demo uses a deterministic synthetic dataset. The public version accepts changes to sample records in an in-memory database; changes may reset when a Worker restarts and are not shared across isolates. Do not enter real personal, farm or business information. The former `/agri` URL redirects here, and old deep links redirect to their matching new routes.

The demo lets reviewers explore the buyer-demand queue, filter coffee offers, inspect farm profiles, stage and submit synthetic allocations, add crop history, register sample farms and manage the input catalog. Changes use an in-memory database and may reset when the Worker restarts. PDF exports remain available only in the local version. Do not enter real personal, farm or buyer information.

## Local application

The full Flask application runs with a local SQLite database and includes record creation, allocation, input-catalog management, demo reset and PDF exports.

```bash
git clone https://github.com/malique-spooner/agri-platform.git
cd agri-platform
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements-local.txt
python database/setup_database.py
python database/generate_data.py
python app.py
```

Then open [http://localhost:5000/](http://localhost:5000/). The generated people and records are synthetic. The local app writes to `database/app_data.db`; that database is ignored by Git and can be regenerated with `python database/generate_data.py`.

`requirements-local.txt` includes ReportLab and pytest for local PDF exports and project development. The Cloudflare Worker dependencies are declared separately in `pyproject.toml`.

## Cloudflare Worker

The Worker mounts Flask beneath `/Origin-Acre` and creates an in-memory SQLite database from the deterministic sample data for each isolate. The interactive demo accepts changes to synthetic data; those changes can reset when an isolate restarts and are not shared across isolates. The landing page and HTML templates and static files are copied into the Worker asset bundle before local preview or deploy. Former `/agri` links are permanently redirected to their matching `/Origin-Acre` routes.

```bash
uv sync
python scripts/build_worker_assets.py
uv run pywrangler dev
```

For deployment, run `bash scripts/deploy_worker.sh` after confirming the Cloudflare account and route in `wrangler.jsonc`. The script stages only the Worker source, vendored dependencies, and public assets so local virtual environments are not uploaded.

## Technology

- Python 3.11+
- Flask and SQLite for the local application
- Cloudflare Workers Python runtime for the public interactive demo
- ReportLab for local PDF exports
- Pytest for the local project test suite
