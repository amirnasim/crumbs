"""Enqueue SMS work to Celery — never blocks the request cycle."""

from django.conf import settings


def dispatch_sms_event(
    event_code: str,
    recipient: str,
    context: dict,
    *,
    user=None,
    order=None,
    dedupe_key: str | None = None,
):
    from notifications.tasks import send_sms_event_task

    if dedupe_key is None and order is not None:
        dedupe_key = f"{order.pk}:{event_code}"
    elif dedupe_key is None:
        dedupe_key = f"{recipient}:{event_code}"

    kwargs = {
        "event_code": event_code,
        "recipient": recipient,
        "context": context,
        "user_id": user.pk if user else None,
        "order_id": order.pk if order else None,
        "dedupe_key": dedupe_key,
    }
    options = {"queue": "sms"}
    if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        options["task_id"] = f"sms:{dedupe_key}"[:255]
    return send_sms_event_task.apply_async(kwargs=kwargs, **options)


def dispatch_template_sms(
    template_code: str,
    recipient: str,
    context: dict,
    *,
    user=None,
    order=None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
):
    from notifications.tasks import send_template_sms_task

    if dedupe_key is None:
        dedupe_key = f"{recipient}:{template_code}"

    kwargs = {
        "template_code": template_code,
        "recipient": recipient,
        "context": context,
        "user_id": user.pk if user else None,
        "order_id": order.pk if order else None,
        "metadata": metadata,
        "dedupe_key": dedupe_key,
    }
    options = {"queue": "sms"}
    if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        options["task_id"] = f"sms:{dedupe_key}"[:255]
    return send_template_sms_task.apply_async(kwargs=kwargs, **options)


def dispatch_raw_sms(
    recipient: str,
    message: str,
    *,
    template_code: str = "",
    user=None,
    order=None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
):
    from notifications.tasks import send_sms_task

    if dedupe_key is None:
        dedupe_key = f"{recipient}:{template_code or 'raw'}"

    kwargs = {
        "recipient": recipient,
        "message": message,
        "template_code": template_code,
        "user_id": user.pk if user else None,
        "order_id": order.pk if order else None,
        "metadata": metadata,
        "dedupe_key": dedupe_key,
    }
    options = {"queue": "sms"}
    if not getattr(settings, "CELERY_TASK_ALWAYS_EAGER", False):
        options["task_id"] = f"sms:{dedupe_key}"[:255]
    return send_sms_task.apply_async(kwargs=kwargs, **options)
