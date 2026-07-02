import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from core.tasks.base import CrumbsTask
from notifications.services import SMSService, send_sms, send_template_sms

logger = logging.getLogger("crumbs.tasks")
User = get_user_model()


@shared_task(base=CrumbsTask, bind=True, name="notifications.tasks.send_sms_event_task")
def send_sms_event_task(
    self,
    event_code: str,
    recipient: str,
    context: dict,
    *,
    user_id=None,
    order_id=None,
    dedupe_key: str | None = None,
):
    user = User.objects.filter(pk=user_id).first() if user_id else None
    order = None
    if order_id:
        from orders.models import Order

        order = Order.objects.filter(pk=order_id).first()

    result = SMSService.send_event(
        event_code,
        recipient,
        context,
        user=user,
        order=order,
        metadata={"task_id": self.request.id},
    )
    return {"log_id": result.pk if result else None, "event_code": event_code}


@shared_task(base=CrumbsTask, bind=True, name="notifications.tasks.send_sms_task")
def send_sms_task(
    self,
    recipient: str,
    message: str,
    *,
    template_code: str = "",
    user_id=None,
    order_id=None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
):
    user = User.objects.filter(pk=user_id).first() if user_id else None
    order = None
    if order_id:
        from orders.models import Order

        order = Order.objects.filter(pk=order_id).first()

    log = send_sms(
        recipient,
        message,
        template_code=template_code,
        user=user,
        order=order,
        metadata={**(metadata or {}), "task_id": self.request.id},
        dedupe_key=dedupe_key,
    )
    return {"log_id": log.pk, "status": log.status}


@shared_task(base=CrumbsTask, bind=True, name="notifications.tasks.send_template_sms_task")
def send_template_sms_task(
    self,
    template_code: str,
    recipient: str,
    context: dict,
    *,
    user_id=None,
    order_id=None,
    metadata: dict | None = None,
    dedupe_key: str | None = None,
):
    user = User.objects.filter(pk=user_id).first() if user_id else None
    order = None
    if order_id:
        from orders.models import Order

        order = Order.objects.filter(pk=order_id).first()

    log = send_template_sms(
        template_code,
        recipient,
        context,
        user=user,
        order=order,
        metadata={**(metadata or {}), "task_id": self.request.id},
        dedupe_key=dedupe_key,
    )
    return {"log_id": log.pk if log else None, "status": log.status if log else None}


@shared_task(base=CrumbsTask, name="notifications.tasks.retry_failed_sms_task")
def retry_failed_sms_task():
    retried = SMSService.retry_failed()
    logger.info("Retried failed SMS", extra={"count": retried})
    return {"retried": retried}
