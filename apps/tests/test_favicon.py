import pytest
from django.urls import reverse

@pytest.mark.django_db
def test_favicon_redirect(client):
    """
    Test that /favicon.ico redirects to the static favicon.svg.
    """
    response = client.get("/favicon.ico")
    assert response.status_code == 301
    assert response["Location"] == "/static/favicon.svg"

@pytest.mark.django_db
def test_api_root_works(client):
    """
    Test that the API root still works correctly.
    """
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["name"] == "BookForBook API"
