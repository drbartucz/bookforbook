import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

# Allow the custom domain, the Railway-assigned domain, and localhost for health checks
_allowed = ["bookforbook.com", "www.bookforbook.com", "api.bookforbook.com"]
_railway_domain = config("RAILWAY_PUBLIC_DOMAIN", default="")
if _railway_domain:
    _allowed.append(_railway_domain)
ALLOWED_HOSTS = _allowed

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
X_FRAME_OPTIONS = "DENY"

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
ANYMAIL = {
    "RESEND_API_KEY": config("RESEND_API_KEY", default=""),
}
DEFAULT_FROM_EMAIL = config(
    "DEFAULT_FROM_EMAIL", default="Book for Book <noreply@bookforbook.com>"
)

# Frontend URL (for email links)
FRONTEND_URL = config("FRONTEND_URL", default="https://bookforbook.com")

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
