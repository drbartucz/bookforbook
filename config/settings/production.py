import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = False

# Allow the custom domain, the Railway-assigned domain, and localhost for health checks
_allowed = ['bookforbook.com', 'www.bookforbook.com', 'api.bookforbook.com']
_railway_domain = config('RAILWAY_PUBLIC_DOMAIN', default='')
if _railway_domain:
    _allowed.append(_railway_domain)
ALLOWED_HOSTS = _allowed

# WhiteNoise — serve and compress static files directly from gunicorn
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# Security settings
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
X_FRAME_OPTIONS = 'DENY'

# Railway terminates TLS at the proxy — tell Django to trust the forwarded header
# instead of redirecting in an infinite loop
SECURE_SSL_REDIRECT = True
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


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

# Email — Proton Mail SMTP submission
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST', default='smtp.protonmail.ch')
EMAIL_PORT = config('EMAIL_PORT', default=587, cast=int)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD', default='')
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=True, cast=bool)
DEFAULT_FROM_EMAIL = config('DEFAULT_FROM_EMAIL', default='noreply@bookforbook.com')

# Frontend URL (for email links)
FRONTEND_URL = config('FRONTEND_URL', default='https://bookforbook.com')

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
        'apps': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}
