"""
Django settings for sanoa project.

This module uses environment-specific settings.
Set ENVIRONMENT variable to: development, production, or testing

All settings are defined in project_config/ (base.py, development.py, production.py, testing.py).
Do NOT add settings here - add them to the appropriate project_config file instead.
"""
from decouple import config

# Get environment (default to development)
ENVIRONMENT = config('ENVIRONMENT', default='development')

# Import environment-specific settings
# Each environment file imports from project_config.base first
if ENVIRONMENT == 'production':
    from project_config.production import *  # noqa: F401,F403
elif ENVIRONMENT == 'testing':
    from project_config.testing import *  # noqa: F401,F403
else:
    from project_config.development import *  # noqa: F401,F403

# Ensure logs directory exists
LOGS_DIR = BASE_DIR / 'logs'  # noqa: F405
LOGS_DIR.mkdir(exist_ok=True)
