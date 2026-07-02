"""Async dispatch helpers for background tasks."""

from core.tasks.observability import claim_idempotency_key


def apply_idempotent_task(task, *, idempotency_key: str, kwargs: dict | None = None, queue: str | None = None):
    """
    Enqueue a Celery task once per idempotency_key.
    Returns AsyncResult or None when skipped.
    """
    kwargs = kwargs or {}
    task_id = idempotency_key[:255]
    if not claim_idempotency_key(
        idempotency_key,
        task_name=task.name,
        task_id=task_id,
        payload=kwargs,
    ):
        return None

    options = {"task_id": task_id}
    if queue:
        options["queue"] = queue
    return task.apply_async(kwargs=kwargs, **options)
