import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'


def _parse_db_url(url: str) -> dict:
    """Parse a DATABASE_URL string into Django DATABASES config."""
    pattern = re.compile(
        r'(?P<scheme>postgres(?:ql)?)://(?P<user>[^:]+):(?P<password>[^@]*)@'
        r'(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<name>[^?]+)'
    )
    match = pattern.match(url)
    if not match:
        raise ValueError(f'Invalid DATABASE_URL: {url!r}')
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': match.group('name'),
        'USER': match.group('user'),
        'PASSWORD': match.group('password'),
        'HOST': match.group('host'),
        'PORT': match.group('port') or '5432',
        'OPTIONS': {'sslmode': 'require'},
        'CONN_MAX_AGE': 600,
    }


DATABASE_URL = config('DATABASE_URL')
DATABASES = {'default': _parse_db_url(DATABASE_URL)}

# Email backend — real SMTP in production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'WARNING',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
