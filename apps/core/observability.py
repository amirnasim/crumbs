"""Structured logging helpers and optional Sentry initialization."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

# Fields allowed in JSON log output (operational IDs only).
OPS_LOG_FIELDS = frozenset(
    {
        "event",
        "request_path",
        "order_id",
        "payment_id",
        "provider",
        "status",
        "outcome",
        "task_id",
        "task_name",
        "examined",
        "cleaned",
        "skipped",
        "errors",
        "timeout_minutes",
        "report_date",
        "sent",
        "updated",
        "kwargs_keys",
        "retries",
        "dead_letter",
        "idempotency_key",
    }
)

_SENSITIVE_KEY_RE = re.compile(
    r"(password|secret|token|authorization|cookie|resume|email|phone|address|"
    r"postal|cvv|card|ssn|body|payload)",
    re.IGNORECASE,
)

_EMAIL_RE = re.compile(r"[^\s@]+@[^\s@]+\.[^\s@]+")


def scrub_mapping(data: dict[str, Any], *, depth: int = 0) -> dict[str, Any]:
    """Remove sensitive keys from a dict before sending to Sentry."""
    if depth > 6:
        return {"truncated": True}

    cleaned: dict[str, Any] = {}
    for key, value in data.items():
        if _SENSITIVE_KEY_RE.search(str(key)):
            cleaned[key] = "[Filtered]"
            continue
        if isinstance(value, dict):
            cleaned[key] = scrub_mapping(value, depth=depth + 1)
        elif isinstance(value, list):
            cleaned[key] = [
                scrub_mapping(item, depth=depth + 1) if isinstance(item, dict) else "[Filtered]"
                if _SENSITIVE_KEY_RE.search(str(item))
                else item
                for item in value[:20]
            ]
        else:
            cleaned[key] = value
    return cleaned


def sentry_before_send(event: dict[str, Any], hint: dict[str, Any]) -> dict[str, Any] | None:
    """Strip PII and request bodies before events reach Sentry."""
    request = event.get("request")
    if isinstance(request, dict):
        request.pop("data", None)
        request.pop("cookies", None)
        headers = request.get("headers")
        if isinstance(headers, dict):
            for header in ("Authorization", "Cookie", "X-CSRFToken"):
                headers.pop(header, None)
        event["request"] = scrub_mapping(request)

    extra = event.get("extra")
    if isinstance(extra, dict):
        event["extra"] = scrub_mapping(extra)

    breadcrumbs = event.get("breadcrumbs")
    if isinstance(breadcrumbs, dict):
        values = breadcrumbs.get("values")
        if isinstance(values, list):
            for crumb in values:
                if isinstance(crumb, dict) and "data" in crumb:
                    crumb["data"] = scrub_mapping(crumb.get("data") or {})

    return event


def init_sentry(
    *,
    dsn: str,
    environment: str,
    release: str | None,
    traces_sample_rate: float,
) -> None:
    """Initialize Sentry when DSN is configured; no-op otherwise."""
    if not dsn:
        return

    import sentry_sdk
    from sentry_sdk.integrations.celery import CeleryIntegration
    from sentry_sdk.integrations.django import DjangoIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration

    sentry_sdk.init(
        dsn=dsn,
        integrations=[
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
        traces_sample_rate=traces_sample_rate,
        send_default_pii=False,
        environment=environment,
        release=release or None,
        before_send=sentry_before_send,
    )


class JsonFormatter(logging.Formatter):
    """Docker-friendly JSON logs with optional operational fields."""

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "time": self.formatTime(record, self.datefmt),
            "logger": record.name,
            "message": record.getMessage(),
        }

        for key in OPS_LOG_FIELDS:
            if key in record.__dict__:
                payload[key] = record.__dict__[key]

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=False)


def log_payment_event(
    event: str,
    *,
    order_id: int | None = None,
    payment_id: int | None = None,
    provider: str | None = None,
    status: str | None = None,
    request_path: str | None = None,
    outcome: str | None = None,
) -> None:
    """Safe payment lifecycle log — IDs only, no customer PII."""
    extra: dict[str, Any] = {"event": event}
    if order_id is not None:
        extra["order_id"] = order_id
    if payment_id is not None:
        extra["payment_id"] = payment_id
    if provider:
        extra["provider"] = provider
    if status:
        extra["status"] = status
    if request_path:
        extra["request_path"] = request_path
    if outcome:
        extra["outcome"] = outcome

    logging.getLogger("crumbs.payments").info(event, extra=extra)


def log_order_event(
    event: str,
    *,
    order_id: int,
    status: str | None = None,
    outcome: str | None = None,
) -> None:
    """Safe order lifecycle log — IDs only."""
    extra: dict[str, Any] = {"event": event, "order_id": order_id}
    if status:
        extra["status"] = status
    if outcome:
        extra["outcome"] = outcome

    logging.getLogger("crumbs.orders").info(event, extra=extra)


def message_contains_pii(message: str) -> bool:
    """Heuristic used in tests — detect obvious PII in log text."""
    lowered = message.lower()
    if _EMAIL_RE.search(message):
        return True
    for token in ("password=", "resume_file", "authorization:", "streetaddress"):
        if token in lowered:
            return True
    return False
