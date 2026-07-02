"""Order lifecycle event emission — decouples HTTP from SMS, loyalty, analytics."""

from delivery.state_machine import STATUS_LABELS_FA
from orders.models import Order
from orders.services.order_service import OrderService


def _resolve_phone(order: Order) -> str:
    if order.phone:
        return order.phone
    if order.user_id:
        return getattr(getattr(order.user, "profile", None), "phone", "")
    return ""


def _base_context(order: Order) -> dict:
    return {
        "name": order.first_name or "مشتری",
        "order_number": order.order_number,
        "total": int(order.total),
    }


def build_order_lifecycle_events(
    order: Order,
    *,
    created: bool,
    prev_payment,
    prev_status,
) -> list[dict]:
    phone = _resolve_phone(order)
    if not phone:
        return []

    context = _base_context(order)
    events: list[dict] = []

    if created:
        events.append(
            {
                "kind": "sms_event",
                "event_code": "order_created",
                "phone": phone,
                "context": context,
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        )
        return events

    paid_states = {Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED}
    if order.payment_status in paid_states and prev_payment not in paid_states:
        events.append(
            {
                "kind": "sms_event",
                "event_code": "payment_success",
                "phone": phone,
                "context": context,
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        )
        events.append({"kind": "abandoned_cart_recovered", "order_id": order.pk})
        events.append({"kind": "loyalty_award", "order_id": order.pk})
        events.append({"kind": "growth_finalize", "order_id": order.pk})
        events.append({"kind": "analytics_touch", "order_id": order.pk, "event": "payment_success"})

    elif (
        order.payment_status == Order.PaymentStatus.COD_CONFIRMED
        and prev_payment != Order.PaymentStatus.COD_CONFIRMED
    ):
        events.append(
            {
                "kind": "sms_event",
                "event_code": "order_confirmed_by_shop",
                "phone": phone,
                "context": context,
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        )

    elif order.payment_status == Order.PaymentStatus.FAILED and prev_payment != Order.PaymentStatus.FAILED:
        events.append(
            {
                "kind": "sms_event",
                "event_code": "payment_failed",
                "phone": phone,
                "context": context,
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        )

    elif (
        order.payment_status == Order.PaymentStatus.REFUND_PROCESSED
        and prev_payment != Order.PaymentStatus.REFUND_PROCESSED
    ):
        events.append(
            {
                "kind": "sms_event",
                "event_code": "refund_processed",
                "phone": phone,
                "context": context,
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        )
        events.append({"kind": "analytics_touch", "order_id": order.pk, "event": "refund_processed"})

    status_changed = order.status != prev_status
    if status_changed:
        event_code = OrderService.sms_event_for_status(order.status)
        if event_code:
            events.append(
                {
                    "kind": "sms_event",
                    "event_code": event_code,
                    "phone": phone,
                    "context": {
                        **context,
                        "status": STATUS_LABELS_FA.get(order.status, order.status),
                    },
                    "user_id": order.user_id,
                    "order_id": order.pk,
                }
            )
            events.append(
                {
                    "kind": "analytics_touch",
                    "order_id": order.pk,
                    "event": f"status:{order.status}",
                }
            )

        if (
            order.status == Order.Status.OUT_FOR_DELIVERY
            and order.is_cod
            and order.payment_status == Order.PaymentStatus.COD_CONFIRMED
        ):
            events.append(
                {
                    "kind": "sms_event",
                    "event_code": "cod_reminder",
                    "phone": phone,
                    "context": context,
                    "user_id": order.user_id,
                    "order_id": order.pk,
                }
            )

    if status_changed and order.status == Order.Status.DELIVERED:
        events.append({"kind": "analytics_touch", "order_id": order.pk, "event": "delivered"})

    return events


def _idempotency_key(order: Order, events: list[dict], prev_payment, prev_status) -> str:
    event_codes = ",".join(
        sorted(
            e.get("event_code") or e.get("kind") or e.get("event", "")
            for e in events
        )
    )
    return (
        f"order-lifecycle:{order.pk}:"
        f"{prev_payment}:{order.payment_status}:"
        f"{prev_status}:{order.status}:{event_codes}"
    )


def emit_order_lifecycle_events(
    order: Order,
    *,
    created: bool = False,
    prev_payment=None,
    prev_status=None,
) -> None:
    """Enqueue async processing for order side-effects."""
    import logging

    logger = logging.getLogger(__name__)

    try:
        events = build_order_lifecycle_events(
            order,
            created=created,
            prev_payment=prev_payment,
            prev_status=prev_status,
        )
        if not events:
            return

        from core.tasks.dispatch import apply_idempotent_task
        from orders.tasks import process_order_lifecycle_events

        idempotency_key = _idempotency_key(order, events, prev_payment, prev_status)
        apply_idempotent_task(
            process_order_lifecycle_events,
            idempotency_key=idempotency_key,
            kwargs={"order_id": order.pk, "events": events},
            queue="orders",
        )
    except Exception:
        logger.exception(
            "Failed to enqueue order lifecycle notifications for order %s",
            order.order_number,
        )
