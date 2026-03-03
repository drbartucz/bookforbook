import re

from decouple import config

from .base import *  # noqa: F401, F403

DEBUG = True

ALLOWED_HOSTS = ['*']

# Database — parse DATABASE_URL manually (no external lib dependency)
DATABASE_URL = config('DATABASE_URL', default='')


def _parse_db_url(url: str) -> dict:
    """Simple DATABASE_URL parser that supports postgresql:// and postgres:// schemes."""
    pattern = re.compile(
        r'(?P<scheme>postgres(?:ql)?)://(?P<user>[^:]+):(?P<password>[^@]*)@'
        r'(?P<host>[^:/]+)(?::(?P<port>\d+))?/(?P<name>[^?]+)'
    )
    match = pattern.match(url)
    if not match:
        return {}
    return {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': match.group('name'),
        'USER': match.group('user'),
        'PASSWORD': match.group('password'),
        'HOST': match.group('host'),
        'PORT': match.group('port') or '5432',
    }


if DATABASE_URL:
    db_config = _parse_db_url(DATABASE_URL)
    if db_config:
        DATABASES = {'default': db_config}
    else:
        DATABASES = {
            'default': {
                'ENGINE': 'django.db.backends.sqlite3',
                'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
            }
        }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
        }
    }

# Email backend — print to console in development
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'

# Less strict CORS in development
CORS_ALLOW_ALL_ORIGINS = True

# Logging
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'apps': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': False,
        },
    },
}
