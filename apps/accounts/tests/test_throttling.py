"""
Tests for per-endpoint auth throttle classes.

DRF caches DEFAULT_THROTTLE_RATES in SimpleRateThrottle.THROTTLE_RATES at
module import time, so override_settings won't affect the rate lookup.
Instead, we patch get_rate() on each throttle class to force a low limit.

development.py sets DummyCache so throttle counts don't accumulate across
the test suite. Throttle-specific tests therefore switch to LocMemCache
(via the `settings` fixture) for the duration of each test so that cache
operations actually persist and the throttle can fire.
"""

import pytest
from django.conf import settings
from django.core.cache import cache
from unittest.mock import patch
from rest_framework import status
from rest_framework.test import APIClient

from apps.accounts.throttles import (
    LoginRateThrottle,
    PasswordResetRateThrottle,
    RegisterRateThrottle,
)

_LOCMEM_CACHE = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "throttle-tests",
    }
}


# ---------------------------------------------------------------------------
# Settings-level tests — verify scopes are configured with the right rates
# ---------------------------------------------------------------------------


class TestThrottleSettings:
    def test_auth_login_scope_configured(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        assert "auth_login" in rates
        assert rates["auth_login"] == "10/hour"

    def test_auth_register_scope_configured(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        assert "auth_register" in rates
        assert rates["auth_register"] == "5/hour"

    def test_auth_password_reset_scope_configured(self):
        rates = settings.REST_FRAMEWORK.get("DEFAULT_THROTTLE_RATES", {})
        assert "auth_password_reset" in rates
        assert rates["auth_password_reset"] == "5/hour"

    def test_throttle_class_scopes(self):
        assert LoginRateThrottle.scope == "auth_login"
        assert RegisterRateThrottle.scope == "auth_register"
        assert PasswordResetRateThrottle.scope == "auth_password_reset"


# ---------------------------------------------------------------------------
# Integration tests — verify throttle classes are wired to views and fire
# ---------------------------------------------------------------------------


@pytest.mark.django_db
class TestLoginThrottle:
    url = "/api/v1/auth/token/"

    def test_throttle_blocks_after_limit(self, settings):
        settings.CACHES = _LOCMEM_CACHE
        cache.clear()
        with patch.object(LoginRateThrottle, "get_rate", return_value="2/minute"):
            client = APIClient()
            payload = {"email": "x@example.com", "password": "wrong"}
            for _ in range(2):
                client.post(self.url, payload)
            resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestRegisterThrottle:
    url = "/api/v1/auth/register/"

    def test_throttle_blocks_after_limit(self, settings):
        settings.CACHES = _LOCMEM_CACHE
        cache.clear()
        with patch.object(RegisterRateThrottle, "get_rate", return_value="2/minute"):
            client = APIClient()
            payload = {
                "email": "a@gmail.com",
                "username": "userA",
                "password": "StrongPass1!",
                "password2": "StrongPass1!",
            }
            for _ in range(2):
                client.post(self.url, payload)
            resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
class TestPasswordResetThrottle:
    url = "/api/v1/auth/password-reset/"

    def test_throttle_blocks_after_limit(self, settings):
        settings.CACHES = _LOCMEM_CACHE
        cache.clear()
        with patch.object(
            PasswordResetRateThrottle, "get_rate", return_value="2/minute"
        ):
            client = APIClient()
            payload = {"email": "nobody@example.com"}
            for _ in range(2):
                client.post(self.url, payload)
            resp = client.post(self.url, payload)
        assert resp.status_code == status.HTTP_429_TOO_MANY_REQUESTS
