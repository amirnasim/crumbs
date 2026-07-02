import logging
from datetime import datetime

from django.utils import timezone

from core.models import BackgroundTaskLog

logger = logging.getLogger("crumbs.tasks")


def claim_idempotency_key(idempotency_key: str, *, task_name: str, task_id: str, payload: dict | None = None) -> bool:
    """
    Return True if this task should run; False if an equivalent task already
    completed or is in-flight.
    """
    if not idempotency_key:
        return True

    existing = BackgroundTaskLog.objects.filter(idempotency_key=idempotency_key).first()
    if existing and existing.status in {
        BackgroundTaskLog.Status.PENDING,
        BackgroundTaskLog.Status.STARTED,
        BackgroundTaskLog.Status.SUCCESS,
    }:
        logger.info(
            "Skipping duplicate task",
            extra={"idempotency_key": idempotency_key, "task_name": task_name},
        )
        return False

    BackgroundTaskLog.objects.update_or_create(
        idempotency_key=idempotency_key,
        defaults={
            "task_name": task_name,
            "task_id": task_id,
            "status": BackgroundTaskLog.Status.PENDING,
            "payload": payload or {},
        },
    )
    return True


def mark_task_started(task_id: str, *, task_name: str = "") -> None:
    defaults = {"status": BackgroundTaskLog.Status.STARTED, "updated_at": timezone.now()}
    if task_name:
        defaults["task_name"] = task_name
    BackgroundTaskLog.objects.update_or_create(task_id=task_id, defaults=defaults)


def mark_task_success(task_id: str, *, result=None, task_name: str = "") -> None:
    defaults = {
        "status": BackgroundTaskLog.Status.SUCCESS,
        "result": result,
        "completed_at": timezone.now(),
        "updated_at": timezone.now(),
    }
    if task_name:
        defaults["task_name"] = task_name
    BackgroundTaskLog.objects.update_or_create(task_id=task_id, defaults=defaults)


def mark_task_failure(task_id: str, *, error: str, retry_count: int = 0, dead: bool = False, task_name: str = "") -> None:
    status = BackgroundTaskLog.Status.DEAD if dead else BackgroundTaskLog.Status.FAILURE
    defaults = {
        "status": status,
        "error_message": error[:2000],
        "retry_count": retry_count,
        "completed_at": timezone.now() if dead else None,
        "updated_at": timezone.now(),
    }
    if task_name:
        defaults["task_name"] = task_name
    BackgroundTaskLog.objects.update_or_create(task_id=task_id, defaults=defaults)
    if dead:
        logger.error(
            "Task moved to dead-letter queue",
            extra={"task_id": task_id, "error": error, "retry_count": retry_count},
        )


def mark_task_retry(task_id: str, *, retry_count: int, error: str, task_name: str = "") -> None:
    defaults = {
        "status": BackgroundTaskLog.Status.RETRY,
        "retry_count": retry_count,
        "error_message": error[:2000],
        "updated_at": timezone.now(),
    }
    if task_name:
        defaults["task_name"] = task_name
    BackgroundTaskLog.objects.update_or_create(task_id=task_id, defaults=defaults)


def log_task_event(task_name: str, message: str, **extra) -> None:
    payload = {"task": task_name, **extra, "ts": datetime.utcnow().isoformat()}
    logger.info(message, extra=payload)
