"""Tests for the buyer pledges page."""


def test_buyer_pledges_page_returns_success(client):
    """The buyer pledges page should return HTTP 200."""
    response = client.get("/buyer-pledges")

    assert response.status_code == 200
    assert b"Buyer Pledges" in response.data
    assert b"<table>" in response.data
