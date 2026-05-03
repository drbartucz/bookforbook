import pytest
from unittest.mock import patch
from django.urls import reverse
from rest_framework import status
import requests

@pytest.mark.django_db
class TestContactSupportView:
    @pytest.fixture(autouse=True)
    def set_turnstile_key(self, settings):
        settings.TURNSTILE_SECRET_KEY = "test-turnstile-secret-key"

    @property
    def url(self):
        return reverse("contact-support")

    def test_contact_success(self, api_client):
        """Test successful contact form submission."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello, I need help.",
            "turnstile_token": "valid-token"
        }

        with patch("requests.post") as mock_post, \
             patch("apps.notifications.views.send_support_contact_email") as mock_send_email:

            # Mock Turnstile success
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True}

            # Mock Email success
            mock_send_email.return_value = True

            response = api_client.post(self.url, payload, format="json")

            assert response.status_code == status.HTTP_200_OK
            assert response.data["detail"] == "Message sent successfully!"
            mock_send_email.assert_called_once_with("Test User", "test@example.com", "Hello, I need help.")

    def test_contact_missing_fields(self, api_client):
        """Test validation error when fields are missing."""
        payload = {
            "name": "Test User",
            # email missing
            "message": "Hello",
            "turnstile_token": "token"
        }

        response = api_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "All fields are required" in response.data["detail"]

    def test_contact_captcha_failure(self, api_client):
        """Test failure when Turnstile verification fails."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello",
            "turnstile_token": "invalid-token"
        }

        with patch("requests.post") as mock_post:
            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": False}

            response = api_client.post(self.url, payload, format="json")

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Captcha verification failed" in response.data["detail"]

    def test_contact_captcha_network_error(self, api_client):
        """Test 503 error when Turnstile service is down."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello",
            "turnstile_token": "token"
        }

        with patch("requests.post", side_effect=requests.RequestException):
            response = api_client.post(self.url, payload, format="json")
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Verification service unavailable" in response.data["detail"]

    def test_contact_email_failure(self, api_client):
        """Test 500 error when email fails to send after verification."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello",
            "turnstile_token": "valid-token"
        }

        with patch("requests.post") as mock_post, \
             patch("apps.notifications.views.send_support_contact_email") as mock_send_email:

            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True}
            mock_send_email.return_value = False

            response = api_client.post(self.url, payload, format="json")

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to send message" in response.data["detail"]

    def test_contact_invalid_email(self, api_client):
        """Test 400 error when email address is malformed."""
        payload = {
            "name": "Test User",
            "email": "not-an-email",
            "message": "Hello",
            "turnstile_token": "token"
        }

        response = api_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid email address" in response.data["detail"]

    def test_contact_rejects_newlines_in_name(self, api_client):
        """Test that newline characters in name are rejected to prevent header injection."""
        payload = {
            "name": "Evil\nUser",
            "email": "evil@example.com",
            "message": "Hello",
            "turnstile_token": "valid-token"
        }

        response = api_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid characters" in response.data["detail"]

    def test_contact_rejects_newlines_in_email(self, api_client):
        """Test that newline characters in email are rejected to prevent header injection."""
        payload = {
            "name": "Test User",
            "email": "evil\n@example.com",
            "message": "Hello",
            "turnstile_token": "valid-token"
        }

        response = api_client.post(self.url, payload, format="json")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "Invalid characters" in response.data["detail"]

    def test_contact_authenticated_user_is_throttled(self, auth_api_client):
        """Authenticated users should also be subject to the contact throttle (first request succeeds)."""
        payload = {
            "name": "Auth User",
            "email": "auth@example.com",
            "message": "Hello",
            "turnstile_token": "valid-token"
        }

        with patch("requests.post") as mock_post, \
             patch("apps.notifications.views.send_support_contact_email") as mock_send_email:

            mock_post.return_value.status_code = 200
            mock_post.return_value.json.return_value = {"success": True}
            mock_send_email.return_value = True

            # First request should succeed (throttle not yet exceeded)
            response = auth_api_client.post(self.url, payload, format="json")
            assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestContactSupportViewUnconfigured:
    """Tests for when TURNSTILE_SECRET_KEY is not configured."""

    @pytest.fixture(autouse=True)
    def clear_turnstile_key(self, settings):
        settings.TURNSTILE_SECRET_KEY = ""

    def test_contact_returns_503_when_turnstile_unconfigured(self, api_client):
        """Contact endpoint returns 503 when TURNSTILE_SECRET_KEY is not set."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello",
            "turnstile_token": "any-token"
        }
        response = api_client.post(reverse("contact-support"), payload, format="json")
        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        assert "not configured" in response.data["detail"]
