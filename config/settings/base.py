import os
from datetime import timedelta
from pathlib import Path

from decouple import Csv, config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Security
SECRET_KEY = config("SECRET_KEY", default="django-insecure-change-me-in-production")
ALLOWED_HOSTS = config("ALLOWED_HOSTS", default="localhost,127.0.0.1", cast=Csv())

# Application definition
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "anymail",
    "django_q",
    "django_filters",
    "dbbackup",
    "storages",
    "csp",
]

LOCAL_APPS = [
    "apps.accounts",
    "apps.books",
    "apps.inventory",
    "apps.matching",
    "apps.trading",
    "apps.donations",
    "apps.ratings",
    "apps.notifications",
    "apps.messaging",
    "apps.backups",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "csp.middleware.CSPMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

# Custom User Model
AUTH_USER_MODEL = "accounts.User"

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# Internationalization
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# Static files
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

# Media files
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Default primary key field type
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# REST Framework
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.AnonRateThrottle",
        "rest_framework.throttling.UserRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": "60/hour",
        "user": "1000/hour",
        "isbn_lookup": "30/hour",
        # Bot mitigation: tight per-IP limits on sensitive auth endpoints
        "auth_login": "10/hour",
        "auth_register": "5/hour",
        "auth_password_reset": "5/hour",
        "auth_email_verify": "10/hour",
        "auth_reset_confirm": "10/hour",
        "auth_resend_verification": "5/hour",
        "data_export": "5/day",
    },
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
}

# JWT settings
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "UPDATE_LAST_LOGIN": False,
    "ALGORITHM": "HS256",
    "SIGNING_KEY": SECRET_KEY,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "AUTH_HEADER_NAME": "HTTP_AUTHORIZATION",
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}

# CORS
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://localhost:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True
CORS_EXPOSE_HEADERS = ["X-Address-Prompt"]

# Django-Q2 (uses PostgreSQL as broker — no Redis needed)
Q_CLUSTER = {
    "name": "bookforbook",
    "workers": 2,
    "timeout": 300,
    "retry": 360,
    "orm": "default",
    "catch_up": False,
    "max_attempts": 3,
    "ack_failures": True,
}


# Encrypted model fields
FIELD_ENCRYPTION_KEY = config(
    "FIELD_ENCRYPTION_KEY",
    # No default for security. Must be set via environment.
)

# Email settings (defaults match Proton Mail SMTP submission; overridden per environment)
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = config("EMAIL_HOST", default="smtp.protonmail.ch")
EMAIL_PORT = config("EMAIL_PORT", default=587, cast=int)
EMAIL_HOST_USER = config("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = config("EMAIL_HOST_PASSWORD", default="")
EMAIL_USE_TLS = config("EMAIL_USE_TLS", default=True, cast=bool)
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Book for Book <noreply@bookforbook.com>"
)

# Frontend URL (for email links)
FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:5173")

# Admin account activity alerts
ADMIN_ACCOUNT_ALERT_EMAIL = config(
    "ADMIN_ACCOUNT_ALERT_EMAIL", default="john@bookforbook.com"
)
ADMIN_ACCOUNT_ALERTS_ENABLED = config(
    "ADMIN_ACCOUNT_ALERTS_ENABLED", default=True, cast=bool
)
ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS = config(
    "ADMIN_ACCOUNT_ALERTS_SKIP_TEST_USERS", default=True, cast=bool
)
ADMIN_ACCOUNT_ALERT_TEST_DOMAINS = config(
    "ADMIN_ACCOUNT_ALERT_TEST_DOMAINS",
    default="example.com,test.local,example.org",
    cast=Csv(),
)
ADMIN_ACCOUNT_ALERT_TEST_PREFIXES = config(
    "ADMIN_ACCOUNT_ALERT_TEST_PREFIXES",
    default="test,pytest,qa",
    cast=Csv(),
)

# AWS S3 settings (optional)
AWS_ACCESS_KEY_ID = config("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = config("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = config("AWS_STORAGE_BUCKET_NAME", default="")
AWS_S3_REGION_NAME = config("AWS_S3_REGION_NAME", default="us-east-1")

# ─── django-dbbackup ────────────────────────────────────────────────────────
# Keep the 7 most recent database backups; overridden per environment.
DBBACKUP_CLEANUP_KEEP = 7
DBBACKUP_CLEANUP_KEEP_MEDIA = 3
# Default to filesystem storage (overridden to S3 in production).
DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
DBBACKUP_STORAGE_OPTIONS = {"location": str(BASE_DIR / "backups")}

# USPS Developer API (OAuth2 + Addresses v3)
USPS_CLIENT_ID = config("USPS_CLIENT_ID", default="")
USPS_CLIENT_SECRET = config("USPS_CLIENT_SECRET", default="")
USPS_OAUTH_SCOPE = config("USPS_OAUTH_SCOPE", default="")
USPS_OAUTH_BASE_URL = config(
    "USPS_OAUTH_BASE_URL", default="https://apis.usps.com/oauth2/v3"
)
USPS_ADDRESSES_BASE_URL = config(
    "USPS_ADDRESSES_BASE_URL", default="https://apis.usps.com/addresses/v3"
)

# ─── Bot mitigation ─────────────────────────────────────────────────────────
# Minimum account age (in hours) before a user is eligible to appear in match
# detection. New accounts can still browse, list books, and configure their
# profile — they simply will not be matched until this threshold has passed.
MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS = config(
    "MATCH_ELIGIBILITY_MIN_ACCOUNT_AGE_HOURS", default=0, cast=int
)
USPS_API_TIMEOUT = config("USPS_API_TIMEOUT", default=8, cast=int)
