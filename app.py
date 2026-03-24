"""Minimal Flask application for the agricultural coordination prototype."""

import logging

from flask import Flask, render_template

from logic.database_helpers import get_all_buyer_pledges, get_all_farms
from logic.logging_config import configure_logging


configure_logging()
logger = logging.getLogger(__name__)


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__, template_folder="pages")
    logger.info("Flask application created")

    @app.route("/")
    def home():
        """Render the home page."""
        logger.info("Rendering home page")
        return render_template("home.html")

    @app.route("/buyer-pledges")
    def buyer_pledges():
        """Render the buyer pledge listing page."""
        logger.info("Loading buyer pledges page")
        pledges = get_all_buyer_pledges()
        logger.info("Rendering buyer pledges page with %s pledge(s)", len(pledges))
        return render_template("buyer_pledges.html", pledges=pledges)

    @app.route("/farms")
    def farms():
        """Render the farm directory page."""
        logger.info("Loading farm directory page")
        farm_list = get_all_farms()
        logger.info("Rendering farm directory page with %s farm record(s)", len(farm_list))
        return render_template("farms.html", farms=farm_list)

    return app


app = create_app()


if __name__ == "__main__":
    logger.info("Starting development server")
    app.run(debug=True)
