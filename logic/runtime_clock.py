"""Clock helpers that use the Workers host clock when running in Pyodide."""

from datetime import date, datetime, timezone


def today() -> date:
    """Return today's date from the host runtime, with a local Python fallback."""
    try:
        from js import Date as JavaScriptDate

        milliseconds = float(JavaScriptDate.now())
        return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc).date()
    except (ImportError, AttributeError, OverflowError, TypeError, ValueError):
        return date.today()
