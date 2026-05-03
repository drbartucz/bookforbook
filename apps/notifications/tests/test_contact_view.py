import pytest
from unittest.mock import patch, MagicMock
from django.urls import reverse
from rest_framework import status
import requests

@pytest.mark.django_db
class TestContactSupportView:
    @property
    def url(self):
        return reverse("contact-support")

    def test_contact_success(self, client):
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

            response = client.post(self.url, payload)

            assert response.status_code == status.HTTP_200_OK
            assert response.data["detail"] == "Message sent successfully!"
            mock_send_email.assert_called_once_with("Test User", "test@example.com", "Hello, I need help.")

    def test_contact_missing_fields(self, client):
        """Test validation error when fields are missing."""
        payload = {
            "name": "Test User",
            # email missing
            "message": "Hello",
            "turnstile_token": "token"
        }

        response = client.post(self.url, payload)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "All fields are required" in response.data["detail"]

    def test_contact_captcha_failure(self, client):
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

            response = client.post(self.url, payload)

            assert response.status_code == status.HTTP_400_BAD_REQUEST
            assert "Captcha verification failed" in response.data["detail"]

    def test_contact_captcha_network_error(self, client):
        """Test 503 error when Turnstile service is down."""
        payload = {
            "name": "Test User",
            "email": "test@example.com",
            "message": "Hello",
            "turnstile_token": "token"
        }

        with patch("requests.post", side_effect=requests.RequestException):
            response = client.post(self.url, payload)
            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            assert "Verification service unavailable" in response.data["detail"]

    def test_contact_email_failure(self, client):
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

            response = client.post(self.url, payload)

            assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Failed to send message" in response.data["detail"]
