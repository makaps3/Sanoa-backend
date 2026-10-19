"""
Base settings for Sanoa project - shared across all environments
"""
from pathlib import Path
from decouple import config
from datetime import timedelta

# Build paths
BASE_DIR = Path(__file__).resolve().parent.parent

# Security
SECRET_KEY = config(
    'SECRET_KEY',
    default=None  # Requires explicit setting
)
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable must be set. "
        "Generate one with: python -c 'from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())'"
    )

DEBUG = config('DEBUG', default=False, cast=bool)
ALLOWED_HOSTS = config(
    'ALLOWED_HOSTS',
    # `.ngrok-free.dev` allows any tunnel subdomain (matches the
    # leading-dot wildcard rule documented in Django's
    # ALLOWED_HOSTS — `.example.com` covers `foo.example.com`).
    # Without this, requests forwarded by ngrok hit Django with
    # `Host: <tunnel>.ngrok-free.dev` and get rejected with
    # `400 Bad Request (Invalid HTTP_HOST header)` before any view
    # runs — that's why the mobile app sees `127.0.0.1:8101` in
    # backend logs but nothing else: Django binds locally but
    # disallows the ngrok host.
    default=(
        'localhost,127.0.0.1,'
        '105.246.241.64,192.168.18.62,'
        '.ngrok-free.dev,.ngrok-free.app,.ngrok.io'
    ),
    cast=lambda v: [s.strip() for s in v.split(',')]
)

# Application definition
INSTALLED_APPS = [
    # daphne must precede django.contrib.staticfiles
    'daphne',
    'channels',

    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Monitoring
    'django_prometheus',

    # Third party apps
    'rest_framework',
    'rest_framework_simplejwt',
    'rest_framework_simplejwt.token_blacklist',
    'corsheaders',
    'django_filters',
    'drf_spectacular',

    # Local apps
    'accounts',
    'business',
    'fraud',
    'products',
    'orders',
    'restaurant',
    'payments',
    'inventory',
    'debit',
    'subscriptions',
    'negotiations',
    'core',
    'otp',
    'tiers',
    'audit',
    'delivery',
    'notifications',
    'platform_admin',
    'analytics',
    'chat',
    'tickets',
    'promotions',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    
    # Custom middleware
    'audit.middleware.AuditMiddleware',
    'core.middleware.RequestLoggingMiddleware',
    'core.middleware.APIExceptionMiddleware',
    'core.middleware.SuspendedUserMiddleware',
    'core.middleware.SecurityHeadersMiddleware',
    'core.middleware.NoCacheMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'sanoa.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'sanoa.wsgi.application'
ASGI_APPLICATION = 'sanoa.asgi.application'

# Django Channels — Redis channel layer for WebSocket broadcasting
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [config('REDIS_URL', default='redis://localhost:6379/1')],
        },
    },
}

# Database - can be overridden in environment-specific settings
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        # SQLite serialises writes. A busy timeout makes a writer WAIT up to
        # 30s for the lock instead of instantly raising "database is locked";
        # WAL mode (set on each connection in core.apps) lets reads run
        # concurrently with a writer. Together these remove the lock errors
        # seen under concurrent requests on the ASGI server.
        'OPTIONS': {
            'timeout': 30,
        },
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
        'OPTIONS': {
            'min_length': 8,
        }
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True
# Static files
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]

# Media files
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# Default primary key field type
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Custom User Model
AUTH_USER_MODEL = 'accounts.User'

# REST Framework Configuration
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.authentication.VerifiedJWTAuthentication',
        'core.authentication.APITokenAuthentication',
        'core.authentication.VerifiedSessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_PAGINATION_CLASS': 'core.pagination.StandardPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
        'rest_framework.renderers.BrowsableAPIRenderer',
    ],
    # Humanizes error responses platform-wide (friendly `detail` + structured
    # `errors`). NOTE: DRF reads `EXCEPTION_HANDLER`, not the mis-named
    # `DEFAULT_EXCEPTION_HANDLER` that was previously (silently) ignored.
    'EXCEPTION_HANDLER': 'core.exception_handler.humanized_exception_handler',
    'TEST_REQUEST_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_THROTTLE_CLASSES': [
        'rest_framework.throttling.AnonRateThrottle',
        'rest_framework.throttling.UserRateThrottle'
    ],
    'DEFAULT_THROTTLE_RATES': {
        'anon': '100/hour',
        'user': '1000/hour'
    },
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
}

# drf-spectacular (OpenAPI documentation)
SPECTACULAR_SETTINGS = {
    'TITLE': 'Sanoa E-Commerce API',
    'DESCRIPTION': 'REST API for the Sanoa multi-vendor e-commerce platform',
    'VERSION': '1.0.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'COMPONENT_SPLIT_REQUEST': True,
    'SCHEMA_PATH_PREFIX': '/api/',
}

# JWT Configuration
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=60),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS': True,
    'BLACKLIST_AFTER_ROTATION': True,
    'UPDATE_LAST_LOGIN': True,
    'ALGORITHM': 'HS256',
    'SIGNING_KEY': SECRET_KEY,
    'VERIFYING_KEY': None,
    'AUTH_HEADER_TYPES': ('Bearer',),
    'USER_ID_FIELD': 'id',
    'USER_ID_CLAIM': 'user_id',
    'AUTH_TOKEN_CLASSES': ('rest_framework_simplejwt.tokens.AccessToken',),
    'TOKEN_TYPE_CLAIM': 'token_type',
}

# CORS Configuration
CORS_ALLOWED_ORIGINS = [
    'http://localhost:3000',
    'http://127.0.0.1:3000',
    'http://localhost:8080',
    'http://127.0.0.1:8080',
]
# Match every ngrok tunnel subdomain — the host changes whenever a
# new tunnel is opened, so an exact list would go stale fast.
CORS_ALLOWED_ORIGIN_REGEXES = [
    r'^https://[a-z0-9-]+\.ngrok-free\.dev$',
    r'^https://[a-z0-9-]+\.ngrok-free\.app$',
    r'^https://[a-z0-9-]+\.ngrok\.io$',
]

CORS_ALLOW_CREDENTIALS = True

# The Flutter app sends `ngrok-skip-browser-warning` on every request
# (to bypass the ngrok free-tier interstitial). Browsers reject the
# CORS preflight unless that custom header is explicitly allowed.
from corsheaders.defaults import default_headers  # noqa: E402

CORS_ALLOW_HEADERS = list(default_headers) + [
    'ngrok-skip-browser-warning',
]

# CSRF — Django checks the `Origin` header against this list on
# every POST/PUT/PATCH/DELETE. ngrok-forwarded POSTs (login,
# payouts, etc) get rejected with `CSRF verification failed`
# unless the tunnel host is whitelisted here. Schemes are
# required; wildcards are honoured.
CSRF_TRUSTED_ORIGINS = [
    'https://*.ngrok-free.dev',
    'https://*.ngrok-free.app',
    'https://*.ngrok.io',
]

# Email Configuration — Resend SMTP (port 465 = implicit SSL).
# Credentials must come from environment variables or the local .env file.
EMAIL_BACKEND = config(
    'EMAIL_BACKEND',
    default='django.core.mail.backends.smtp.EmailBackend'
)
EMAIL_HOST = config('EMAIL_HOST', default='smtp.resend.com')
EMAIL_PORT = config('EMAIL_PORT', default=465, cast=int)
EMAIL_USE_SSL = config('EMAIL_USE_SSL', default=True, cast=bool)
EMAIL_USE_TLS = config('EMAIL_USE_TLS', default=False, cast=bool)
EMAIL_HOST_USER = config('EMAIL_HOST_USER', default='resend')
EMAIL_HOST_PASSWORD = config(
    'EMAIL_HOST_PASSWORD',
    default='',
)
EMAIL_TIMEOUT = config('EMAIL_TIMEOUT', default=15, cast=int)

# From: "Makaps <onboarding@resend.dev>". `onboarding@resend.dev` is
# Resend's pre-verified test sender, so it works before you verify your own
# domain. In Resend test mode delivery is restricted to your account email
# (lindamakapela3@gmail.com) — verify a domain to send to anyone.
EMAIL_FROM_NAME = config('EMAIL_FROM_NAME', default='Sanoa')
EMAIL_FROM_ADDRESS = config(
    'EMAIL_FROM_ADDRESS', default='onboarding@resend.dev',
)
# Recipient allow-listed by Resend while testing (your account email).
EMAIL_TEST_RECIPIENT = config(
    'EMAIL_TEST_RECIPIENT', default='',
)
# While testing, redirect EVERY outgoing branded email to this address so
# they actually arrive in Resend test mode (which only delivers to your
# account email). Set EMAIL_REDIRECT_ALL='' in .env for production so real
# recipients receive their mail.
EMAIL_REDIRECT_ALL = config(
    'EMAIL_REDIRECT_ALL', default='',
)
DEFAULT_FROM_EMAIL = config(
    'DEFAULT_FROM_EMAIL',
    default=f'{EMAIL_FROM_NAME} <{EMAIL_FROM_ADDRESS}>',
)
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Brand tokens surfaced to email templates.
SANOA_BRAND = {
    'primary': '#219ebc',
    'primary_dark': '#023047',
    'accent': '#f59e0b',
    'name': 'Sanoa',
}
# Public base URL used in email links (deep-links / web).
SANOA_SITE_URL = config('SANOA_SITE_URL', default='https://sanoa.co.za')

# Logging Configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
        'simple': {
            'format': '{levelname} {asctime} {name} {message}',
            'style': '{',
        },
        'json': {
            '()': 'pythonjsonlogger.jsonlogger.JsonFormatter',
            'format': '%(asctime)s %(name)s %(levelname)s %(message)s'
        }
    },
    'filters': {
        'require_debug_false': {
            '()': 'django.utils.log.RequireDebugFalse',
        },
        'require_debug_true': {
            '()': 'django.utils.log.RequireDebugTrue',
        },
    },
    'handlers': {
        'console': {
            'level': 'INFO',
            'class': 'core.logging.UTF8StreamHandler',
            'formatter': 'simple',
        },
        'file': {
            'level': 'INFO',
            'class': 'core.logging.WindowsSafeRotatingFileHandler',
            'filename': BASE_DIR / 'logs' / 'app.log',
            'maxBytes': 1024 * 1024 * 10,  # 10MB
            'backupCount': 5,
            'formatter': 'verbose',
            'delay': True,
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
        'sanoa': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG',
            'propagate': False,
        },
        'sanoa.audit': {
            'handlers': ['console', 'file'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Caching
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
        'LOCATION': 'sanoa-cache',
        'TIMEOUT': 300,  # 5 minutes
    }
}

# Paystack Configuration
PAYSTACK_SECRET_KEY = config('PAYSTACK_SECRET_KEY', default='')
PAYSTACK_PUBLIC_KEY = config('PAYSTACK_PUBLIC_KEY', default='')
PAYSTACK_BASE_URL = config('PAYSTACK_BASE_URL', default='https://api.paystack.co')
PAYSTACK_WEBHOOK_SECRET = config('PAYSTACK_WEBHOOK_SECRET', default='')
PAYSTACK_CALLBACK_URL = config('PAYSTACK_CALLBACK_URL', default='')
PAYSTACK_CURRENCY = 'ZAR'

# Google Maps / Geocoding
#
# Used by `core.geocoding.geocode_address` to convert a textual address
# (street, city, province, country) into (lat, lng) when the client
# doesn't supply coordinates on shipping/business address creation.
# Without this key the geocoder is a no-op and rows save with
# latitude/longitude = NULL.
GOOGLE_MAPS_API_KEY = config('GOOGLE_MAPS_API_KEY', default='')

# Celery Configuration
CELERY_BROKER_URL = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 300  # 5 minutes

CELERY_BEAT_SCHEDULE = {
    'expire-unpaid-subscriptions': {
        'task': 'subscriptions.tasks.enforce_overdue_subscriptions',
        'schedule': 60,
    },
    'disable-expired-paystack-subscriptions': {
        'task': 'subscriptions.tasks.process_subscription_cancellations',
        'schedule': 60,
    },
    'expire-old-negotiations': {
        'task': 'negotiations.tasks.expire_old_negotiations',
        'schedule': 3600,       # every hour
    },
    'retrain-negotiation-models': {
        'task': 'negotiations.tasks.retrain_negotiation_models',
        'schedule': 604800,     # every 7 days
    },
    # Fraud detection
    'fraud-rescore-users': {
        'task': 'fraud.rescore_all_users',
        'schedule': 86400,      # daily
    },
    'fraud-rescore-vendors': {
        'task': 'fraud.rescore_all_vendors',
        'schedule': 86400,      # daily
    },
    'fraud-retrain-models': {
        'task': 'fraud.retrain_models',
        'schedule': 604800,     # weekly
    },
    # Notifications
    'notifications-negotiation-reminders': {
        'task': 'notifications.send_negotiation_reminders',
        'schedule': 3600,       # every hour
    },
    'notifications-subscription-expiry-warnings': {
        'task': 'notifications.send_subscription_expiry_warnings',
        'schedule': 86400,      # daily
    },
    'notifications-subscription-due-soon': {
        'task': 'notifications.send_subscription_due_soon_alerts',
        'schedule': 3600,       # every hour
    },
    'notifications-low-credit-alerts': {
        'task': 'notifications.send_low_credit_alerts',
        'schedule': 86400,      # daily
    },
    'notifications-overdue-credit-reminders': {
        'task': 'notifications.send_overdue_credit_reminders',
        'schedule': 86400,      # daily
    },
    'notifications-vendor-tier-expiry-warnings': {
        'task': 'notifications.send_vendor_tier_expiry_warnings',
        'schedule': 86400,      # daily
    },
    # Analytics — ML scoring (automated, do not touch fraud/negotiations scoring)
    'analytics-daily-snapshot': {
        'task': 'analytics.compute_daily_snapshot',
        'schedule': 86400,      # daily at 02:00 UTC (offset via crontab if needed)
    },
    'analytics-customer-churn-scoring': {
        'task': 'analytics.score_customer_churn',
        'schedule': 604800,     # weekly
    },
    'analytics-vendor-performance-scoring': {
        'task': 'analytics.score_vendor_performance',
        'schedule': 604800,     # weekly
    },
    'analytics-driver-performance-scoring': {
        'task': 'analytics.score_driver_performance',
        'schedule': 604800,     # weekly
    },
    # Payments — prune failed payouts older than 48h so the admin
    # queue doesn't accumulate dead rows. Manual deletion via the
    # admin screen still works at any time.
    'payments-prune-failed-payouts': {
        'task': 'payments.prune_failed_payouts',
        'schedule': 3600,       # every hour
    },
}
