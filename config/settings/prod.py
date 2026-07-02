"""Production settings for CRUMBS."""

import json
import logging
import warnings

from .base import *  # noqa: F403

# ---------------------------------------------------------------------------
# Production safety
# ---------------------------------------------------------------------------

DEBUG = False

if env_bool("DEBUG", default=False):  # noqa: F405
    raise ValueError(
        "DEBUG must be False in config.settings.prod. "
        "Never run production with DEBUG=True — admin and error pages would leak secrets."
    )

LOCAL_PROD_DRY_RUN = env_bool("LOCAL_PROD_DRY_RUN", default=False)  # noqa: F405
_LOCAL_ALLOWED_HOSTS = frozenset({"localhost", "127.0.0.1", "0.0.0.0"})


def _allowed_hosts_is_local_only(hosts) -> bool:
    return not hosts or set(hosts) <= _LOCAL_ALLOWED_HOSTS


if _allowed_hosts_is_local_only(ALLOWED_HOSTS):  # noqa: F405
    if LOCAL_PROD_DRY_RUN:
        warnings.warn(
            "ALLOWED_HOSTS is localhost-only (LOCAL_PROD_DRY_RUN=True). "
            "Set real domain(s) before VPS deploy.",
            stacklevel=1,
        )
    else:
        raise ValueError(
            "ALLOWED_HOSTS must include your production domain(s). "
            "For local Docker dry-run only, set LOCAL_PROD_DRY_RUN=True in .env."
        )
elif not ALLOWED_HOSTS:  # noqa: F405
    raise ValueError("ALLOWED_HOSTS must not be empty in production.")

# ---------------------------------------------------------------------------
# Reverse proxy / TLS (two-phase deploy: HTTP first, HTTPS after SSL)
# ---------------------------------------------------------------------------

ENABLE_HTTPS = env_bool("ENABLE_HTTPS", default=False)  # noqa: F405

if env_bool("SECURE_SSL_REDIRECT", default=False) and not ENABLE_HTTPS:  # noqa: F405
    raise ValueError("SECURE_SSL_REDIRECT=True requires ENABLE_HTTPS=True.")

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
USE_X_FORWARDED_HOST = env_bool("USE_X_FORWARDED_HOST", default=True)  # noqa: F405
USE_X_FORWARDED_PORT = env_bool("USE_X_FORWARDED_PORT", default=True)  # noqa: F405

if ENABLE_HTTPS:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", default=True)  # noqa: F405
    # Ignore stale Phase 1 .env values once HTTPS is enabled.
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    _hsts_seconds = env_int("SECURE_HSTS_SECONDS", 31536000)  # noqa: F405
    SECURE_HSTS_SECONDS = _hsts_seconds if _hsts_seconds > 0 else 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)  # noqa: F405
    SECURE_HSTS_PRELOAD = env_bool("SECURE_HSTS_PRELOAD", default=False)  # noqa: F405

    if not SITE_URL.startswith("https://"):  # noqa: F405
        raise ValueError("ENABLE_HTTPS=True requires SITE_URL to start with https://")

    if not CSRF_TRUSTED_ORIGINS:  # noqa: F405
        raise ValueError("ENABLE_HTTPS=True requires CSRF_TRUSTED_ORIGINS to be set.")
else:
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_SECONDS = 0
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False

# ---------------------------------------------------------------------------
# Security headers & cookies
# ---------------------------------------------------------------------------

SESSION_COOKIE_HTTPONLY = True
# CSRF tokens are read from hidden form fields; HttpOnly on the cookie is safe and recommended.
CSRF_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "strict-origin-when-cross-origin"

# ---------------------------------------------------------------------------
# Admin & user uploads
# ---------------------------------------------------------------------------
# Admin stays at /admin/ by default. For extra hardening after launch, consider a custom
# admin URL via nginx location rules or django-admin-tools (not configured here).
#
# MEDIA_URL / MEDIA_ROOT serve user uploads (e.g. career PDF resumes). Django validates
# PDF magic bytes on upload; nginx must alias /media/ as static files only — never proxy
# uploads through a script handler. See docker/nginx/conf.d/*.template and
# DEPLOYMENT_ENV_CHECKLIST.md.

# ---------------------------------------------------------------------------
# Static files — WhiteNoise fallback when nginx is not serving static
# ---------------------------------------------------------------------------

USE_WHITENOISE = env_bool("USE_WHITENOISE", default=False)  # noqa: F405

if USE_WHITENOISE:
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
    STORAGES = {  # noqa: F405
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
        },
    }

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------

DATABASES["default"]["CONN_MAX_AGE"] = env_int("DB_CONN_MAX_AGE", 600)  # noqa: F405

# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------

MIDDLEWARE.insert(1, "django.middleware.gzip.GZipMiddleware")  # noqa: F405
MIDDLEWARE.append("core.middleware.request_log_context.RequestLogContextMiddleware")  # noqa: F405
MIDDLEWARE.append("core.middleware.rate_limit.RateLimitMiddleware")  # noqa: F405

# ---------------------------------------------------------------------------
# Redis cache (required in production when REDIS_URL is set)
# ---------------------------------------------------------------------------

if not REDIS_URL:  # noqa: F405
    import warnings

    warnings.warn(
        "REDIS_URL is not set. Production will use LocMem cache (not suitable for multi-worker).",
        stacklevel=1,
    )

if not os.environ.get("CELERY_BROKER_URL"):  # noqa: F405
    import warnings

    warnings.warn(
        "CELERY_BROKER_URL is not set. Background jobs will not run in production.",
        stacklevel=1,
    )

# ---------------------------------------------------------------------------
# Sentry (optional — set SENTRY_DSN in environment)
# ---------------------------------------------------------------------------

SENTRY_DSN = os.environ.get("SENTRY_DSN", "")  # noqa: F405
SENTRY_ENVIRONMENT = os.environ.get("SENTRY_ENVIRONMENT", "production")  # noqa: F405
SENTRY_RELEASE = os.environ.get("SENTRY_RELEASE", "") or os.environ.get("APP_VERSION", "")  # noqa: F405

if SENTRY_DSN:
    from core.observability import init_sentry

    init_sentry(
        dsn=SENTRY_DSN,
        environment=SENTRY_ENVIRONMENT,
        release=SENTRY_RELEASE or None,
        traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.1")),  # noqa: F405
    )

# ---------------------------------------------------------------------------
# Iran-first payments (production defaults)
# ---------------------------------------------------------------------------

STRIPE_ENABLED = env_bool("STRIPE_ENABLED", default=False)  # noqa: F405
ZARINPAL_SANDBOX = env_bool("ZARINPAL_SANDBOX", default=False)  # noqa: F405

if not os.environ.get("DEFAULT_PAYMENT_PROVIDER") and not os.environ.get("PAYMENT_PROVIDER"):  # noqa: F405
    DEFAULT_PAYMENT_PROVIDER = "zarinpal"  # noqa: F405
    PAYMENT_PROVIDER = DEFAULT_PAYMENT_PROVIDER  # noqa: F405

if DEFAULT_PAYMENT_PROVIDER == "stripe" and not STRIPE_ENABLED:  # noqa: F405
    raise ValueError(
        "DEFAULT_PAYMENT_PROVIDER=stripe requires STRIPE_ENABLED=True in production."
    )

if STRIPE_ENABLED:  # noqa: F405
    import warnings

    warnings.warn(
        "STRIPE_ENABLED=True in production. Stripe should remain optional/sandbox only for Iran deployments.",
        stacklevel=1,
    )

# ---------------------------------------------------------------------------
# Structured logging
# ---------------------------------------------------------------------------

from core.observability import JsonFormatter  # noqa: E402,F401

LOGGING["filters"] = {  # noqa: F405
    "request_path": {
        "()": "core.middleware.request_log_context.RequestPathLogFilter",
    },
}

LOGGING["formatters"]["json"] = {  # noqa: F405
    "()": "core.observability.JsonFormatter",
}

LOGGING["handlers"]["console"]["formatter"] = "json"  # noqa: F405
LOGGING["handlers"]["console"]["filters"] = ["request_path"]  # noqa: F405

LOGGING["handlers"]["file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / "django.log",  # noqa: F405
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 10,
    "formatter": "json",
    "filters": ["request_path"],
}

LOGGING["handlers"]["request_file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / "requests.log",  # noqa: F405
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 5,
    "formatter": "json",
    "filters": ["request_path"],
}

LOGGING["root"]["handlers"] = ["console", "file"]  # noqa: F405
LOGGING["loggers"]["django"]["handlers"] = ["console", "file"]  # noqa: F405
LOGGING["loggers"]["django.request"] = {  # noqa: F405
    "handlers": ["console", "file", "request_file"],
    "level": "WARNING",
    "propagate": False,
}
LOGGING["loggers"]["gunicorn.error"] = {  # noqa: F405
    "handlers": ["console", "file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["gunicorn.access"] = {  # noqa: F405
    "handlers": ["console", "request_file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["crumbs.tasks"] = {  # noqa: F405
    "handlers": ["console", "file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["celery"] = {  # noqa: F405
    "handlers": ["console", "file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["handlers"]["celery_file"] = {  # noqa: F405
    "class": "logging.handlers.RotatingFileHandler",
    "filename": LOGS_DIR / "celery.log",  # noqa: F405
    "maxBytes": 10 * 1024 * 1024,
    "backupCount": 10,
    "formatter": "json",
    "filters": ["request_path"],
}
LOGGING["loggers"]["crumbs.payments"] = {  # noqa: F405
    "handlers": ["console", "file", "celery_file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["crumbs.orders"] = {  # noqa: F405
    "handlers": ["console", "file", "celery_file"],
    "level": LOG_LEVEL,  # noqa: F405
    "propagate": False,
}
LOGGING["loggers"]["crumbs.tasks"]["handlers"] = ["console", "file", "celery_file"]  # noqa: F405
LOGGING["loggers"]["celery"]["handlers"] = ["console", "file", "celery_file"]  # noqa: F405
