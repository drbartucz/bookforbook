import re
from urllib.parse import urlparse

from decouple import Csv, config
from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F401, F403

DEBUG = False

_INSECURE_DEFAULT_SECRET_KEY = "django-insecure-change-me-in-production"
_INSECURE_DEFAULT_FIELD_ENCRYPTION_KEY = "NmzoBw3C4Rvblhs8AsAsnF-GYGVQatPZnEuvj_aZZUE="

if SECRET_KEY == _INSECURE_DEFAULT_SECRET_KEY:  # noqa: F405
    raise ImproperlyConfigured("SECRET_KEY must be set via environment in production.")

if FIELD_ENCRYPTION_KEY == _INSECURE_DEFAULT_FIELD_ENCRYPTION_KEY:  # noqa: F405
    raise ImproperlyConfigured(
        "FIELD_ENCRYPTION_KEY must be set via environment in production."
    )

# Allow the custom domain, the Railway-assigned domain, and localhost for health checks
_allowed = ["bookforbook.com", "www.bookforbook.com", "api.bookforbook.com"]
_railway_domain = config("RAILWAY_PUBLIC_DOMAIN", default="")
if _railway_domain:
    _allowed.append(_railway_domain)
ALLOWED_HOSTS = _allowed


def _origin_hostname(origin: str) -> str:
    parsed = urlparse(origin)
    return (parsed.hostname or "").lower()


if not CORS_ALLOWED_ORIGINS:  # noqa: F405
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS must be explicitly set in production."
    )

_invalid_cors_origins = []
for _origin in CORS_ALLOWED_ORIGINS:  # noqa: F405
    _host = _origin_hostname(_origin)
    if not _host or _host in {"localhost", "127.0.0.1", "0.0.0.0"}:
        _invalid_cors_origins.append(_origin)

if _invalid_cors_origins:
    raise ImproperlyConfigured(
        "CORS_ALLOWED_ORIGINS cannot include localhost/loopback in production: "
        f"{', '.join(_invalid_cors_origins)}"
    )

CSRF_TRUSTED_ORIGINS = config(
    "CSRF_TRUSTED_ORIGINS",
    default=",".join(CORS_ALLOWED_ORIGINS),  # noqa: F405
    cast=Csv(),
)

if not CSRF_TRUSTED_ORIGINS:
    raise ImproperlyConfigured(
        "CSRF_TRUSTED_ORIGINS must be explicitly set in production."
    )

# WhiteNoise — serve and compress static files directly from gunicorn
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"
SECURE_CROSS_ORIGIN_OPENER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"

CONTENT_SECURITY_POLICY = {
    "DIRECTIVES": {
        "default-src": ["'none'"],
        "connect-src": ["'self'"],
        "frame-ancestors": ["'none'"],
        "form-action": ["'self'"],
    },
}

# Railway terminates TLS at the proxy — tell Django to trust the forwarded header
# instead of redirecting in an infinite loop
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


def _parse_db_url(url: str) -> dict:
    """Parse a DATABASE_URL string into Django DATABASES config.

    Supports TCP:    postgresql://user:pass@host:5432/dbname
    Supports socket: postgresql://user:pass@/dbname?host=/path/to/socket/dir
    """
    pattern = re.compile(
        r"(?P<scheme>postgres(?:ql)?)://(?P<user>[^:]+):(?P<password>[^@]*)@"
        r"(?P<host>[^:/]*)(?::(?P<port>\d+))?/(?P<name>[^?]+)"
        r"(?:\?host=(?P<socketdir>[^&\s]+))?"
    )
    match = pattern.match(url)
    if not match:
        raise ValueError(f"Invalid DATABASE_URL: {url!r}")
    socket_dir = match.group("socketdir")
    host = socket_dir or match.group("host") or ""
    options: dict = {"CONN_MAX_AGE": 600}
    if not socket_dir:
        options["OPTIONS"] = {"sslmode": "require"}
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": match.group("name"),
        "USER": match.group("user"),
        "PASSWORD": match.group("password"),
        "HOST": host,
        "PORT": match.group("port") or "",
        **options,
    }


DATABASE_URL = config("DATABASE_URL")
DATABASES = {"default": _parse_db_url(DATABASE_URL)}

# Email — Resend via django-anymail (HTTP API, no SMTP port restrictions)
EMAIL_BACKEND = "anymail.backends.resend.EmailBackend"
RESEND_API_KEY = config("RESEND_API_KEY", default="")
if not RESEND_API_KEY:
    raise ImproperlyConfigured("RESEND_API_KEY must be set in production.")

ANYMAIL = {
    "RESEND_API_KEY": RESEND_API_KEY,
}
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Book for Book <noreply@bookforbook.com>"
)

# Frontend URL (for email links)
FRONTEND_URL = config("FRONTEND_URL", default="https://bookforbook.com")
_frontend_url = urlparse(FRONTEND_URL)
if _frontend_url.scheme != "https" or not _frontend_url.netloc:
    raise ImproperlyConfigured("FRONTEND_URL must be a valid HTTPS URL in production.")

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {module} {process:d} {thread:d} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "WARNING",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "django_q": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}

# ─── django-dbbackup (Backblaze B2) ──────────────────────────────────────────
# Backblaze B2 is S3-compatible and ~75% cheaper than AWS S3 for backups.
# Set these in Railway env vars:
#   B2_APPLICATION_KEY_ID
#   B2_APPLICATION_KEY
#   B2_BUCKET_NAME
_b2_key_id = config("B2_APPLICATION_KEY_ID", default="")
_b2_key = config("B2_APPLICATION_KEY", default="")
_b2_bucket = config("B2_BUCKET_NAME", default="")

if _b2_key_id and _b2_key and _b2_bucket:
    DBBACKUP_STORAGE = "storages.backends.s3boto3.S3Boto3Storage"
    DBBACKUP_STORAGE_OPTIONS = {
        "access_key": _b2_key_id,
        "secret_key": _b2_key,
        "bucket_name": _b2_bucket,
        "endpoint_url": "https://f000.backblazeb2.com",  # B2's S3-compatible endpoint
        "location": "db-backups",
        "default_acl": "private",
        "file_overwrite": False,
    }
else:
    # Fallback: use filesystem if B2 not configured
    DBBACKUP_STORAGE = "django.core.files.storage.FileSystemStorage"
    DBBACKUP_STORAGE_OPTIONS = {"location": str(BASE_DIR / "backups")}  # noqa: F405
