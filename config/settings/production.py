import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

ALLOWED_HOSTS = ['bookforbook.com', 'www.bookforbook.com', 'api.bookforbook.com']

# WhiteNoise — serve and compress static files directly from gunicorn
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

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
    """Parse a DATABASE_URL string into Django DATABASES config.

    Supports TCP:    postgresql://user:pass@host:5432/dbname
    Supports socket: postgresql://user:pass@/dbname?host=/path/to/socket/dir
    """
    pattern = re.compile(
        r'(?P<scheme>postgres(?:ql)?)://(?P<user>[^:]+):(?P<password>[^@]*)@'
        r'(?P<host>[^:/]*)(?::(?P<port>\d+))?/(?P<name>[^?]+)'
        r'(?:\?host=(?P<socketdir>[^&\s]+))?'
    )
    match = pattern.match(url)
    if not match:
        raise ValueError(f'Invalid DATABASE_URL: {url!r}')
    socket_dir = match.group('socketdir')
    host = socket_dir or match.group('host') or ''
    options: dict = {'CONN_MAX_AGE': 600}
    if not socket_dir:
        options['OPTIONS'] = {'sslmode': 'require'}
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': match.group('name'),
        'USER': match.group('user'),
        'PASSWORD': match.group('password'),
        'HOST': host,
        'PORT': match.group('port') or '',
        **options,
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
