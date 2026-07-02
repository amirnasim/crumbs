"""Development settings for CRUMBS."""

from .base import *  # noqa: F403

DEBUG = True

ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "localhost,127.0.0.1,0.0.0.0")  # noqa: F405

# Local dev uses PostgreSQL (see .env / docker-compose db service).
# Values match base.py — POSTGRES_* env vars, default host localhost:5432.

# Dev uses database sessions (no Redis required locally)
SESSION_ENGINE = "django.contrib.sessions.backends.db"

CACHES = {  # noqa: F811
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "crumbs-dev",
    }
}

INTERNAL_IPS = ["127.0.0.1", "localhost"]

TEMPLATES[0]["OPTIONS"]["context_processors"].insert(  # noqa: F405
    0,
    "django.template.context_processors.debug",
)

EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Run Celery tasks synchronously in dev when no broker is configured.
CELERY_TASK_ALWAYS_EAGER = env_bool("CELERY_TASK_ALWAYS_EAGER", default=True)  # noqa: F405
CELERY_TASK_EAGER_PROPAGATES = True

LOG_LEVEL = "DEBUG"  # noqa: F405
LOGGING["root"]["level"] = LOG_LEVEL  # noqa: F405
LOGGING["loggers"]["django"]["level"] = LOG_LEVEL  # noqa: F405
LOGGING["loggers"]["django.db.backends"] = {  # noqa: F405
    "handlers": ["console"],
    "level": "WARNING",
    "propagate": False,
}
