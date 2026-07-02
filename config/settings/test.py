"""Test settings for CRUMBS production-grade test suite."""

import os

from .base import *  # noqa: F403

DEBUG = False

SECRET_KEY = "test-secret-key-not-for-production-use-only"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "testserver"]

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
# Default: in-memory SQLite for fast local/CI runs.
# Set CRUMBS_TEST_POSTGRES=1 to exercise select_for_update concurrency tests.
if os.environ.get("CRUMBS_TEST_POSTGRES") == "1":
    _test_pg_name = os.environ.get("TEST_POSTGRES_DB", "crumbs_test")
    DATABASES = {  # noqa: F811
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _test_pg_name,
            "USER": os.environ.get("TEST_POSTGRES_USER", "crumbs"),
            "PASSWORD": os.environ.get("TEST_POSTGRES_PASSWORD", "crumbs"),
            "HOST": os.environ.get("TEST_POSTGRES_HOST", "localhost"),
            "PORT": os.environ.get("TEST_POSTGRES_PORT", "5432"),
            "CONN_MAX_AGE": 0,
            "OPTIONS": {
                "connect_timeout": 10,
            },
            "TEST": {
                "NAME": _test_pg_name,
            },
        }
    }
else:
    DATABASES = {  # noqa: F811
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": ":memory:",
        }
    }

# Fast password hashing in tests
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

# In-memory cache; DB sessions (no Redis required in CI)
SESSION_ENGINE = "django.contrib.sessions.backends.db"
CACHES = {  # noqa: F811
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "crumbs-test",
    }
}

# Celery runs synchronously in tests
CELERY_TASK_ALWAYS_EAGER = True
CELERY_TASK_EAGER_PROPAGATES = True

# Safe external service defaults
SMS_PROVIDER = "console"
SMS_ENABLED = True
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
NOTIFICATIONS_EMAIL_ENABLED = True
PAYMENT_PROVIDER = "stripe"
DEFAULT_PAYMENT_METHOD = "online"
STRIPE_SECRET_KEY = "sk_test_mock"
STRIPE_WEBHOOK_SECRET = "whsec_test_mock"
STRIPE_CURRENCY = "irr"

# Disable Sentry noise
SENTRY_DSN = ""

# Reduce logging noise
LOGGING["root"]["level"] = "WARNING"  # noqa: F405
LOGGING["loggers"]["django"]["level"] = "WARNING"  # noqa: F405
