"""
Production settings for Sanoa project
"""
from .base import *
from django.core.exceptions import ImproperlyConfigured

# Production-specific settings
DEBUG = False

ALLOWED_HOSTS = config('ALLOWED_HOSTS', cast=lambda v: [s.strip() for s in v.split(',')])
if not ALLOWED_HOSTS or any(not host or host == '*' or 'ngrok' in host for host in ALLOWED_HOSTS):
    raise ImproperlyConfigured('Production ALLOWED_HOSTS must contain explicit deployment hosts.')
if len(SECRET_KEY) < 50 or len(set(SECRET_KEY)) < 5 or SECRET_KEY.startswith('django-insecure-'):
    raise ImproperlyConfigured('Use a unique, strong production SECRET_KEY of at least 50 characters.')

# Database - use PostgreSQL in production (configure via environment)
DATABASES = {
    'default': {
        'ENGINE': config('DB_ENGINE', default='django.db.backends.postgresql'),
        'NAME': config('DB_NAME'),
        'USER': config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST': config('DB_HOST'),
        'PORT': config('DB_PORT', default='5432'),
        'ATOMIC_REQUESTS': True,
        'CONN_MAX_AGE': 60,
        'CONN_HEALTH_CHECKS': True,
    }
}
if DATABASES['default']['ENGINE'] != 'django.db.backends.postgresql':
    raise ImproperlyConfigured('Production requires PostgreSQL for transactional verification locks.')

# Email - use real SMTP settings in production
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = config('EMAIL_HOST')
EMAIL_PORT = config('EMAIL_PORT', cast=int)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', cast=bool)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=not EMAIL_USE_TLS, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')
if EMAIL_USE_TLS and EMAIL_USE_SSL:
    raise ImproperlyConfigured('Choose either EMAIL_USE_TLS or EMAIL_USE_SSL, not both.')
if EMAIL_REDIRECT_ALL:
    raise ImproperlyConfigured('EMAIL_REDIRECT_ALL must be empty in production.')

# Security
SECURE_SSL_REDIRECT = config('SECURE_SSL_REDIRECT', default=True, cast=bool)
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_HSTS_SECONDS = config('SECURE_HSTS_SECONDS', default=31536000, cast=int)
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = False
# Enable only behind a trusted proxy that replaces incoming forwarded headers.
if config('TRUST_PROXY_SSL_HEADER', default=False, cast=bool):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_BROWSER_XSS_FILTER = True
SECURE_CONTENT_SECURITY_POLICY = {
    'default-src': ("'self'",),
    'script-src': ("'self'",),
    'style-src': ("'self'", "'unsafe-inline'"),
}

# Logging - file output in production
LOGGING['loggers']['sanoa']['level'] = 'INFO'
LOGGING['loggers']['django']['level'] = 'WARNING'

# CORS - limit origins in production
CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS',
    cast=lambda v: [s.strip() for s in v.split(',')]
)
CORS_ALLOWED_ORIGIN_REGEXES = []
CORS_ALLOW_ALL_ORIGINS = False
CSRF_TRUSTED_ORIGINS = config('CSRF_TRUSTED_ORIGINS', default='',
                              cast=lambda v: [s.strip() for s in v.split(',') if s.strip()])

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': config('REDIS_URL', default='redis://127.0.0.1:6379/1'),
        'TIMEOUT': 3600,  # 1 hour
        'OPTIONS': {
            'CLIENT_CLASS': 'django_redis.client.DefaultClient',
        }
    }
}

# Throttling - strict in production
REST_FRAMEWORK['DEFAULT_THROTTLE_RATES'] = {
    'anon': '100/hour',
    'user': '1000/hour'
}
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = ['rest_framework.renderers.JSONRenderer']
