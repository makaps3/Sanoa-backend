"""
Development settings for Sanoa project
"""
from decouple import config
from django.core.exceptions import ImproperlyConfigured

from .base import *

# Development-specific settings
DEBUG = True

ALLOWED_HOSTS = [
    'localhost',
    '127.0.0.1',
    '192.168.18.62',
    '20.164.32.137',
    '*.local',
    'constrictively-unreproached-kyndall.ngrok-free.dev',
]

# Database - PostgreSQL only (credentials live in .env, which git ignores).
# There is deliberately no SQLite fallback: a missing or wrong DB_ENGINE
# stops startup instead of silently using db.sqlite3.
if config('DB_ENGINE', default='') != 'django.db.backends.postgresql':
    raise ImproperlyConfigured(
        'Set DB_ENGINE=django.db.backends.postgresql (plus DB_NAME, DB_USER, '
        'DB_PASSWORD, DB_HOST, DB_PORT) in .env - development runs on PostgreSQL.'
    )
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST', default='localhost'),
        'PORT': config('DB_PORT', default='5432'),
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}

# Channels — use in-memory layer in dev so we don't require a running Redis.
# Note: cross-process broadcasting (e.g. Celery → WS) won't work here, but
# single-process WebSocket chat is fully functional. For production, base.py
# keeps the Redis-backed layer.
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer',
    },
}

# Email — sends via Resend SMTP by default (inherits base.py). Set
# EMAIL_BACKEND=django.core.mail.backends.console.EmailBackend in your
# .env to print emails to the console instead while developing.
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend',
)

# Logging - verbose output in development
LOGGING['loggers']['sanoa']['level'] = 'DEBUG'
LOGGING['handlers']['console']['level'] = 'DEBUG'

# Allow all CORS origins in development (Flutter web runs on a random
# localhost port, so an explicit origin list can't cover it)
CORS_ALLOW_ALL_ORIGINS = True

CSRF_TRUSTED_ORIGINS = [
    'https://constrictively-unreproached-kyndall.ngrok-free.dev',
]

# Disable throttling in development
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '10000/hour',
    'user': '10000/hour'
}

# Enable debug toolbar if installed
try:
    import debug_toolbar
    INSTALLED_APPS.append('debug_toolbar')
    MIDDLEWARE.insert(0, 'debug_toolbar.middleware.DebugToolbarMiddleware')
    INTERNAL_IPS = ['127.0.0.1']
except ImportError:
    pass
