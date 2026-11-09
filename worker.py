"""Cloudflare Worker entry point for the read-only Agri portfolio demo."""

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

from flask import Response, abort, redirect, request, url_for
from flask.sessions import SessionInterface
from jinja2 import BaseLoader, TemplateNotFound
from pyodide.ffi import run_sync
from workers import wsgi

from app import create_app


class AgriPrefixMiddleware:
    """Mount the Flask app under the portfolio's /agri path."""

    def __init__(self, application: Any, prefix: str = "/agri") -> None:
        self.application = application
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ: dict[str, Any], start_response: Any) -> Any:
        path = environ.get("PATH_INFO", "")
        if path == self.prefix:
            environ["PATH_INFO"] = "/"
        elif path.startswith(f"{self.prefix}/"):
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


class PublicDemoSessionInterface(SessionInterface):
    """Give public GET requests an empty session without issuing cookies."""

    def open_session(self, app: Any, request: Any) -> None:
        return None

    def save_session(self, app: Any, session: Any, response: Any) -> None:
        return None


app = create_app()
app.config["DEMO_READ_ONLY"] = True
app.config["APPLICATION_ROOT"] = "/agri"
app.session_interface = PublicDemoSessionInterface()
app.jinja_loader = WorkerAssetTemplateLoader()


@app.context_processor
def inject_demo_state() -> dict[str, bool]:
    return {"demo_mode": True}


@app.before_request
def keep_public_demo_read_only() -> Any:
    if request.method not in {"GET", "HEAD"}:
        abort(405)
    if request.path in {
        "/farmers/register",
        "/export-lots/new",
        "/buyer-pledges/new",
        "/settings",
    }:
        return redirect(url_for("buyer_pledges"))
    return None


def worker_static_asset(filename: str) -> Any:
    assets = request.environ["workers.env"].ASSETS
    response = run_sync(assets.fetch(f"https://assets.local/static/{filename}"))
    body = run_sync(response.bytes())
    return Response(body, status=response.status, headers=response.headers)


app.view_functions["static"] = worker_static_asset
app.wsgi_app = AgriPrefixMiddleware(app.wsgi_app)
Default = wsgi.entrypoint(app)
