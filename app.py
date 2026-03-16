"""Minimal Flask application for the agricultural coordination prototype."""

from flask import Flask, render_template

from logic.database_helpers import get_all_buyer_pledges, get_all_farms


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)

    @app.route("/")
    def home():
        """Render the home page."""
        return render_template("home.html")

    @app.route("/buyer-pledges")
    def buyer_pledges():
        """Render the buyer pledge listing page."""
        pledges = get_all_buyer_pledges()
        return render_template("buyer_pledges.html", pledges=pledges)

    @app.route("/farms")
    def farms():
        """Render the farm directory page."""
        farm_list = get_all_farms()
        return render_template("farms.html", farms=farm_list)

    return app


app = create_app()


if __name__ == "__main__":
    app.run(debug=True)
