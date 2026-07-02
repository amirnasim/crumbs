import logging

from celery import shared_task
from django.contrib.auth import get_user_model

from core.tasks.base import CrumbsTask
from growth.services import mark_abandoned_cart_recovered
from loyalty.tasks import award_loyalty_points_task
from orders.models import Order

logger = logging.getLogger("crumbs.tasks")
User = get_user_model()


@shared_task(base=CrumbsTask, bind=True, name="orders.tasks.process_order_lifecycle_events")
def process_order_lifecycle_events(self, order_id: int, events: list[dict]):
    """Fan-out order lifecycle work to dedicated async workers."""
    try:
        order = Order.objects.select_related("user").get(pk=order_id)
    except Order.DoesNotExist:
        logger.warning("Order %s not found for lifecycle events", order_id)
        return {"skipped": True, "reason": "order_not_found"}

    dispatched = {"sms": 0, "email": 0, "loyalty": 0, "analytics": 0, "cart": 0, "growth": 0}

    for event in events:
        kind = event.get("kind")
        if kind == "sms_event":
            from notifications.notification_service import NotificationService

            try:
                notification_result = NotificationService.notify_order_event(
                    event["event_code"],
                    order=order,
                    context=event["context"],
                    phone=event.get("phone", ""),
                )
            except Exception:
                logger.exception(
                    "Order notification handler failed for order %s event %s",
                    order.order_number,
                    event.get("event_code"),
                )
                continue

            if notification_result.get("sms_log_id"):
                dispatched["sms"] += 1
            if notification_result.get("email_sent"):
                dispatched["email"] += 1

        elif kind == "loyalty_award":
            award_loyalty_points_task.apply_async(
                kwargs={"order_id": event["order_id"]},
                task_id=f"loyalty:order:{event['order_id']}"[:255],
            )
            dispatched["loyalty"] += 1

        elif kind == "abandoned_cart_recovered":
            mark_abandoned_cart_recovered(order)
            dispatched["cart"] += 1

        elif kind == "analytics_touch":
            from growth.tasks import record_order_analytics_event

            record_order_analytics_event.apply_async(
                kwargs={"order_id": event["order_id"], "event_name": event["event"]},
                task_id=f"analytics:order:{event['order_id']}:{event['event']}"[:255],
                queue="analytics",
            )
            dispatched["analytics"] += 1

        elif kind == "growth_finalize":
            from growth.tasks import finalize_growth_order_task

            finalize_growth_order_task.apply_async(
                kwargs={"order_id": event["order_id"]},
                task_id=f"growth:finalize:{event['order_id']}"[:255],
                queue="analytics",
            )
            dispatched["growth"] += 1

    return dispatched
