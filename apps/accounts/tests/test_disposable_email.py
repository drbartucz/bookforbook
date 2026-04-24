"""
Tests for disposable email domain validation on registration.
"""

import pytest
from rest_framework import status

from apps.accounts.disposable_email_domains import DISPOSABLE_EMAIL_DOMAINS
from apps.accounts.serializers import RegisterSerializer


# ---------------------------------------------------------------------------
# Unit tests — pure validator logic, no DB needed
# ---------------------------------------------------------------------------


class TestDisposableEmailDomainsList:
    def test_known_disposable_domains_are_present(self):
        known = [
            "mailinator.com",
            "guerrillamail.com",
            "yopmail.com",
            "10minutemail.com",
            "temp-mail.org",
            "maildrop.cc",
            "trashmail.com",
        ]
        for domain in known:
            assert domain in DISPOSABLE_EMAIL_DOMAINS, (
                f"{domain} should be in the blocklist"
            )

    def test_legitimate_domains_not_present(self):
        legit = [
            "gmail.com",
            "yahoo.com",
            "outlook.com",
            "hotmail.com",
            "protonmail.com",
            "icloud.com",
            "example.com",
        ]
        for domain in legit:
            assert domain not in DISPOSABLE_EMAIL_DOMAINS


class TestRegisterSerializerDisposableEmailValidation:
    _base_data = {
        "username": "testuser",
        "password": "StrongPass1!",
        "password2": "StrongPass1!",
    }

    def _make_data(self, email):
        return {**self._base_data, "email": email}

    def test_disposable_email_raises_validation_error(self):
        s = RegisterSerializer(data=self._make_data("user@mailinator.com"))
        assert not s.is_valid()
        assert "email" in s.errors
        assert "disposable" in s.errors["email"][0].lower()

    def test_guerrilla_mail_blocked(self):
        s = RegisterSerializer(data=self._make_data("anon@guerrillamail.com"))
        assert not s.is_valid()
        assert "email" in s.errors

    def test_yopmail_blocked(self):
        s = RegisterSerializer(data=self._make_data("anon@yopmail.com"))
        assert not s.is_valid()
        assert "email" in s.errors

    def test_legitimate_email_not_blocked_by_domain(self):
        """The email field itself should not error for a real domain."""
        s = RegisterSerializer(data=self._make_data("real@gmail.com"))
        s.is_valid()
        assert "email" not in s.errors

    def test_mixed_case_domain_blocked(self):
        """Domain comparison must be case-insensitive."""
        s = RegisterSerializer(data=self._make_data("user@MAILINATOR.COM"))
        assert not s.is_valid()
        assert "email" in s.errors

    def test_subdomain_not_blocked(self):
        """Exact-domain matching only — subdomains are not auto-blocked."""
        s = RegisterSerializer(data=self._make_data("user@sub.mailinator.com"))
        s.is_valid()
        assert "email" not in s.errors


# ---------------------------------------------------------------------------
# API integration tests — full register endpoint
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestRegisterViewDisposableEmail:
    url = "/api/v1/auth/register/"

    def test_register_with_disposable_email_returns_400(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "bot@mailinator.com",
                "username": "botuser",
                "password": "StrongPass1!",
                "password2": "StrongPass1!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in resp.data

    def test_register_with_yopmail_returns_400(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "anon@yopmail.com",
                "username": "yopuser",
                "password": "StrongPass1!",
                "password2": "StrongPass1!",
            },
        )
        assert resp.status_code == status.HTTP_400_BAD_REQUEST
        assert "email" in resp.data

    def test_register_with_legitimate_email_succeeds(self, api_client):
        resp = api_client.post(
            self.url,
            {
                "email": "real@gmail.com",
                "username": "realuser",
                "password": "StrongPass1!",
                "password2": "StrongPass1!",
            },
        )
        assert resp.status_code == status.HTTP_201_CREATED
