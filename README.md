# Origin & Acre

A coffee supply-chain coordination prototype for farmer registration, buyer demand, farm offers and lot traceability. This is a student project and a product concept, not a production system or a service used by real farmers or buyers.

## Public demo

The project landing page is [Origin & Acre](https://maliquespooner.com/Origin-Acre/); its read-only demo uses a deterministic synthetic dataset. The public version does not accept farmer or buyer details, save changes, or use a persistent database. Do not enter real personal, farm or business information. The former `/agri` URL redirects here, and old deep links redirect to their matching new routes.

The demo lets reviewers explore the buyer-demand queue, filter coffee offers, inspect farm profiles and walk through the allocation interface. Write actions and PDF exports remain available only in the local version.

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

The Worker mounts Flask beneath `/Origin-Acre`, creates a fresh in-memory SQLite database from the deterministic sample data for each isolate and rejects all non-read requests. The landing page and HTML templates and static files are copied into the Worker asset bundle before local preview or deploy. Former `/agri` links are permanently redirected to their matching `/Origin-Acre` routes.

```bash
uv sync
python scripts/build_worker_assets.py
uv run pywrangler dev
```

For deployment, run `bash scripts/deploy_worker.sh` after confirming the Cloudflare account and route in `wrangler.jsonc`. The script stages only the Worker source, vendored dependencies, and public assets so local virtual environments are not uploaded.

## Technology

- Python 3.11+
- Flask and SQLite for the local application
- Cloudflare Workers Python runtime for the public read-only demo
- ReportLab for local PDF exports
- Pytest for the local project test suite
