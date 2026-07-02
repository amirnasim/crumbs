"""Production health and readiness endpoints (infrastructure only)."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError

from django.conf import settings
from django.db import connections
from django.db.migrations.executor import MigrationExecutor
from django.http import JsonResponse
from django.views.decorators.http import require_GET

CHECK_TIMEOUT_SECONDS = 1.0


def _run_with_timeout(func, timeout: float = CHECK_TIMEOUT_SECONDS) -> None:
    with ThreadPoolExecutor(max_workers=1) as pool:
        future = pool.submit(func)
        future.result(timeout=timeout)


def _check_database() -> tuple[str, bool]:
    def _ping() -> None:
        connection = connections["default"]
        connection.ensure_connection()
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")

    try:
        _run_with_timeout(_ping)
        return "ok", True
    except Exception:
        return "error", False


def _check_redis() -> tuple[str, bool]:
    redis_url = getattr(settings, "REDIS_URL", "")
    if not redis_url:
        return "skipped", True

    def _ping() -> None:
        import redis

        client = redis.from_url(
            redis_url,
            socket_connect_timeout=CHECK_TIMEOUT_SECONDS,
            socket_timeout=CHECK_TIMEOUT_SECONDS,
        )
        client.ping()

    try:
        _run_with_timeout(_ping)
        return "ok", True
    except Exception:
        return "error", False


def _check_celery_broker() -> tuple[str, bool]:
    broker_url = getattr(settings, "CELERY_BROKER_URL", "")
    if not broker_url:
        return "skipped", True

    def _ping() -> None:
        from kombu import Connection

        with Connection(broker_url, connect_timeout=CHECK_TIMEOUT_SECONDS) as conn:
            conn.connect()

    try:
        _run_with_timeout(_ping)
        return "ok", True
    except Exception:
        return "error", False


def _check_migrations() -> tuple[str, bool]:
    try:
        connection = connections["default"]
        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
        if plan:
            return "pending", False
        return "ok", True
    except Exception:
        return "error", False


def _collect_readiness_checks() -> tuple[dict[str, str], bool]:
    db_status, db_ok = _check_database()
    redis_status, redis_ok = _check_redis()
    celery_status, celery_ok = _check_celery_broker()
    migrations_status, migrations_ok = _check_migrations()

    checks = {
        "database": db_status,
        "redis": redis_status,
        "celery_broker": celery_status,
        "migrations": migrations_status,
    }
    ready = db_ok and redis_ok and celery_ok and migrations_ok
    return checks, ready


def _health_full_enabled() -> bool:
    if settings.DEBUG:
        return True
    return os.environ.get("HEALTH_FULL_ENABLED", "").lower() in {"1", "true", "yes"}


@require_GET
def health_check(request):
    """Liveness probe — confirms the Django process is running."""
    return JsonResponse(
        {
            "status": "ok",
            "service": "crumbs",
            "type": "liveness",
        }
    )


@require_GET
def readiness_check(request):
    """Readiness probe — validates production dependencies."""
    checks, ready = _collect_readiness_checks()
    return JsonResponse(
        {
            "status": "ready" if ready else "not_ready",
            "type": "readiness",
            "service": "crumbs",
            "ready": ready,
            "checks": checks,
        },
        status=200 if ready else 503,
    )


@require_GET
def health_full(request):
    """Extended diagnostics for admin/debug (disabled in production by default)."""
    if not _health_full_enabled():
        return JsonResponse({"detail": "Not found."}, status=404)

    checks, ready = _collect_readiness_checks()
    connection = connections["default"]

    payload = {
        "status": "ok" if ready else "degraded",
        "service": "crumbs",
        "type": "full",
        "environment": os.environ.get("DJANGO_SETTINGS_MODULE", "unknown"),
        "debug": settings.DEBUG,
        "database_vendor": connection.vendor,
        "checks": checks,
    }

    version = os.environ.get("APP_VERSION") or getattr(settings, "APP_VERSION", None)
    if version:
        payload["version"] = version

    return JsonResponse(payload, status=200 if ready else 503)
