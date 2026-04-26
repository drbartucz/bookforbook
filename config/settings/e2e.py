"""
config/settings/e2e.py

Django settings for Playwright E2E tests.
Inherits from development but overrides anything that would make tests
non-deterministic or call external services.

Usage:
    DJANGO_SETTINGS_MODULE=config.settings.e2e python manage.py runserver 8000
"""

from .development import *  # noqa: F401, F403

# ── Email — never send real mail ─────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
FRONTEND_URL = "http://localhost:5173"

# ── Django-Q2 — disable background workers entirely ──────────────────────────
# Tasks triggered during tests (matching, notifications) won't run async,
# preventing interference with test state machines.
Q_CLUSTER = {
    "name": "e2e",
    "workers": 0,
    "sync": True,  # execute tasks synchronously in the calling thread
    "orm": "default",
    "timeout": 60,
}

# ── Throttling — raise limits to avoid rate-limit failures in CI ─────────────
REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"] = {  # noqa: F405
    **REST_FRAMEWORK["DEFAULT_THROTTLE_RATES"],  # noqa: F405
    "anon": "600/hour",
    "user": "6000/hour",
    "isbn_lookup": "300/hour",
    "auth_login": "600/hour",
    "auth_register": "300/hour",
    "auth_password_reset": "300/hour",
}

# ── Security — relaxed for local/CI E2E environment only ─────────────────────
ALLOWED_HOSTS = ["*"]
CORS_ALLOWED_ORIGIN_REGEXES = [
    r"^https?://localhost(:\d+)?$",
    r"^https?://127\.0\.0\.1(:\d+)?$",
]
