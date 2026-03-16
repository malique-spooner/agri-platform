"""Tests for the home page."""


def test_home_page_returns_success(client):
    """The home page should return HTTP 200."""
    response = client.get("/")

    assert response.status_code == 200
    assert b"Agricultural Supply Coordination Platform" in response.data
