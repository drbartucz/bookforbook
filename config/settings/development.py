import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ["*"]

# Database — parse DATABASE_URL manually (no external lib dependency)
DATABASE_URL = config("DATABASE_URL", default="")


def _parse_db_url(url: str) -> dict:
    """Simple DATABASE_URL parser that supports postgresql:// and postgres:// schemes.

    Supports TCP:   postgresql://user:pass@host:5432/dbname
    Supports socket: postgresql://user:pass@/dbname?host=/path/to/socket/dir
    """
    pattern = re.compile(
        r"(?P<scheme>postgres(?:ql)?)://(?P<user>[^:]+):(?P<password>[^@]*)@"
        r"(?P<host>[^:/]*)(?::(?P<port>\d+))?/(?P<name>[^?]+)"
        r"(?:\?host=(?P<socketdir>[^&\s]+))?"
    )
    match = pattern.match(url)
    if not match:
        return {}
    host = match.group("socketdir") or match.group("host") or ""
    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": match.group("name"),
        "USER": match.group("user"),
        "PASSWORD": match.group("password"),
        "HOST": host,
        "PORT": match.group("port") or "",
    }


if DATABASE_URL:
    db_config = _parse_db_url(DATABASE_URL)
    if db_config:
        DATABASES = {"default": db_config}
    else:
        DATABASES = {
            "default": {
                "ENGINE": "django.db.backends.sqlite3",
                "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
            }
        }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
        }
    }

# Email backend — print to console in development
EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# CORS: use explicit allowlist from base settings (CORS_ALLOWED_ORIGINS)

# Logging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "apps": {
            "handlers": ["console"],
            "level": "DEBUG",
            "propagate": False,
        },
    },
}

# Disable throttling in development / tests so the full test suite doesn't
# hit rate limits when many tests call the token endpoint in the same hour.
REST_FRAMEWORK["DEFAULT_THROTTLE_CLASSES"] = []  # noqa: F405

# ─── django-dbbackup (local filesystem) ─────────────────────────────────────
# Backups land in <project_root>/backups/ — already set in base.py.
# Nothing extra needed; the directory is created automatically by dbbackup.
