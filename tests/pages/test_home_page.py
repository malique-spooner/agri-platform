"""Tests for the home page."""


def test_home_page_redirects_to_buyer_pledges(client):
    """The home page should redirect to the buyer pledge management view."""
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["Location"].endswith("/buyer-pledges")


def test_health_check_endpoint_returns_ok(client):
    """The deployment health endpoint should return a healthy response."""
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
