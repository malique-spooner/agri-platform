"""Cloudflare Worker entry point for the interactive synthetic Origin & Acre demo."""

from __future__ import annotations

import logging
from pathlib import Path
import sqlite3
from types import SimpleNamespace
from typing import Any

import logic.logging_config as logging_config


def _configure_worker_logging(level: int = logging.INFO) -> Path:
    """Send application logs to the Worker console instead of a local file."""
    logging.getLogger().setLevel(level)
    return Path("/dev/null")


logging_config.configure_logging = _configure_worker_logging

# The demo only exposes deterministic synthetic data and rejects all writes.
# A single in-memory SQLite connection per Worker isolate keeps the existing
# Flask data-access layer intact without relying on isolate-local disk state.
_database = sqlite3.connect(":memory:")
_database.row_factory = sqlite3.Row


def _connect_to_demo_database(*args: Any, **kwargs: Any) -> sqlite3.Connection:
    return _database


sqlite3.connect = _connect_to_demo_database

from database.generate_data import generate_dataset

_demo_database_ready = False


def seed_demo_database(force: bool = False) -> None:
    """Seed or reset synthetic records for a fresh public demo session."""
    global _demo_database_ready
    if _demo_database_ready and not force:
        return
    generate_dataset(
        SimpleNamespace(
            buyers=20,
            buyer_pledges_total=20,
            farmers=45,
            max_buyer_pledges=2,
            max_farmer_pledges=3,
            max_input_logs=5,
            seed=20260324,
            database_path=Path("/tmp/agri-demo.sqlite3"),
        )
    )
    _demo_database_ready = True

from flask import Response, render_template, request, session, url_for
from jinja2 import BaseLoader, TemplateNotFound
from pyodide.ffi import run_sync
from workers import wsgi

from app import create_app


class AgriPrefixMiddleware:
    """Mount Origin & Acre and redirect its former /agri URLs."""

    def __init__(self, application: Any, prefix: str = "/Origin-Acre") -> None:
        self.application = application
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        path = environ.get("PATH_INFO", "")
        legacy_prefix = "/agri"
        if path == self.prefix:
            target = f"{self.prefix}/"
            query = environ.get("QUERY_STRING", "")
            if query:
                target = f"{target}?{query}"
            start_response("301 Moved Permanently", [("Location", target), ("Content-Length", "0")])
            return [b""]
        if path == legacy_prefix or path.startswith(f"{legacy_prefix}/"):
            target = f"{self.prefix}{path[len(legacy_prefix):]}"
            if target == self.prefix:
                target = f"{self.prefix}/"
            query = environ.get("QUERY_STRING", "")
            if query:
                target = f"{target}?{query}"
            start_response("301 Moved Permanently", [("Location", target), ("Content-Length", "0")])
            return [b""]
        if path.startswith(f"{self.prefix}/"):
            environ["PATH_INFO"] = path[len(self.prefix) :]
        else:
            start_response("404 Not Found", [("Content-Type", "text/plain; charset=utf-8")])
            return [b"Not found"]

        environ["SCRIPT_NAME"] = f"{environ.get('SCRIPT_NAME', '')}{self.prefix}"
        return self.application(environ, start_response)


class WorkerAssetTemplateLoader(BaseLoader):
    """Load Flask/Jinja templates from the Worker static asset binding."""

    def get_source(self, environment: Any, template: str) -> tuple[str, str, Any]:
        safe_template = template.replace("..", "").lstrip("/")
        assets = request.environ["workers.env"].ASSETS
        response = run_sync(assets.fetch(f"https://assets.local/pages/{safe_template}"))
        if response.status != 200:
            raise TemplateNotFound(template)
        source = run_sync(response.text())
        return source, f"worker-assets://pages/{safe_template}", lambda: True


app = create_app()
app.config["DEMO_READ_ONLY"] = False
app.config["APPLICATION_ROOT"] = "/Origin-Acre"
app.jinja_loader = WorkerAssetTemplateLoader()


@app.after_request
def prevent_cached_html(response: Any) -> Any:
    if response.mimetype == "text/html":
        response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


def origin_acre_landing() -> Any:
    return render_template("origin-acre-landing.html")


app.view_functions["home"] = origin_acre_landing


@app.context_processor
def inject_demo_state() -> dict[str, bool]:
    return {"demo_mode": True, "interactive_demo": True}


@app.before_request
def seed_public_demo_on_request() -> Any:
    if request.endpoint != "static":
        # Flask's session cookie is a browser-session cookie. Reset the shared,
        # in-memory demo when a visitor starts fresh or opens the landing page
        # again after closing the demo.
        new_browser_session = not session.get("_origin_acre_demo_started")
        restart_from_landing = request.endpoint == "home"
        seed_demo_database(force=_demo_database_ready and (new_browser_session or restart_from_landing))
        session["_origin_acre_demo_started"] = True
    return None


def worker_static_asset(filename: str) -> Any:
    assets = request.environ["workers.env"].ASSETS
    response = run_sync(assets.fetch(f"https://assets.local/static/{filename}"))
    body = run_sync(response.bytes())
    return Response(body, status=response.status, headers=response.headers)


app.view_functions["static"] = worker_static_asset
app.wsgi_app = AgriPrefixMiddleware(app.wsgi_app)
Default = wsgi.entrypoint(app)
