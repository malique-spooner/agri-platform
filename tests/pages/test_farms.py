"""Tests for the farm directory page."""


def test_farms_page_returns_success(client):
    """The farm directory page should return HTTP 200."""
    response = client.get("/farms")

    assert response.status_code == 200
    assert b"Farm Directory" in response.data
    assert b"<ul>" in response.data
