"""Cleanup stale unpaid online checkouts and release reserved stock."""

from __future__ import annotations

import logging
from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from cart.models import Cart
from orders.models import Order
from payments.models import Payment
from payments.services import PaymentService

logger = logging.getLogger(__name__)

STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES = 30

_ONLINE_PROVIDERS = (Payment.Provider.ZARINPAL, Payment.Provider.STRIPE)
_STALE_PAYMENT_STATUSES = (Payment.Status.PENDING, Payment.Status.PROCESSING)
_PROTECTED_ORDER_PAYMENT_STATUSES = {
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.CASH_RECEIVED,
}
_CLEANUP_MESSAGE = (
    "Online checkout expired after "
    f"{STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES} minutes without payment."
)


def get_stale_online_payment_cutoff(*, timeout_minutes: int | None = None):
    minutes = timeout_minutes or STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES
    return timezone.now() - timedelta(minutes=minutes)


def stale_online_payments_queryset(*, cutoff=None):
    """Payments matching ops dashboard stale-online definition."""
    cutoff = cutoff or get_stale_online_payment_cutoff()
    return (
        Payment.objects.filter(
            status__in=_STALE_PAYMENT_STATUSES,
            provider__in=_ONLINE_PROVIDERS,
            created_at__lt=cutoff,
            order__payment_method=Order.PaymentMethod.ONLINE,
        )
        .select_related("order")
        .order_by("created_at")
    )


def _clear_cart_checkout_lock(order_id: int) -> None:
    Cart.objects.filter(active_checkout_order_id=order_id).update(
        active_checkout_order=None,
        updated_at=timezone.now(),
    )


@transaction.atomic
def cleanup_stale_online_payment(payment_id: int) -> str:
    """
    Cancel one stale unpaid online checkout.

    Returns: cleaned | skipped_* outcome token.
    Idempotent for already-failed/cancelled orders and released reservations.
    """
    try:
        payment = Payment.objects.select_for_update().select_related("order").get(pk=payment_id)
    except Payment.DoesNotExist:
        return "skipped_missing"

    order = payment.order
    cutoff = get_stale_online_payment_cutoff()

    if payment.provider not in _ONLINE_PROVIDERS:
        return "skipped_provider"
    if payment.status not in _STALE_PAYMENT_STATUSES:
        return "skipped_payment_status"
    if payment.created_at >= cutoff:
        return "skipped_fresh"
    if order.payment_method != Order.PaymentMethod.ONLINE:
        return "skipped_non_online"
    if order.payment_status in _PROTECTED_ORDER_PAYMENT_STATUSES:
        return "skipped_paid_order"
    if order.status in {Order.Status.CANCELLED, Order.Status.REFUNDED, Order.Status.DELIVERED}:
        return "skipped_terminal_order"

    PaymentService.mark_failed(order, payment, _CLEANUP_MESSAGE)
    _clear_cart_checkout_lock(order.pk)
    logger.info(
        "Stale online payment cleaned",
        extra={"payment_id": payment_id, "order_id": order.pk, "outcome": "cleaned"},
    )
    return "cleaned"


def cleanup_stale_online_payments(*, timeout_minutes: int | None = None) -> dict:
    """Run stale online payment cleanup for all matching payments."""
    cutoff = get_stale_online_payment_cutoff(timeout_minutes=timeout_minutes)
    payment_ids = list(stale_online_payments_queryset(cutoff=cutoff).values_list("pk", flat=True))

    cleaned = 0
    skipped = 0
    errors = 0

    for payment_id in payment_ids:
        try:
            outcome = cleanup_stale_online_payment(payment_id)
        except Exception:
            errors += 1
            logger.exception(
                "Failed to cleanup stale online payment",
                extra={"payment_id": payment_id},
            )
            continue

        if outcome == "cleaned":
            cleaned += 1
        else:
            skipped += 1

    result = {
        "examined": len(payment_ids),
        "cleaned": cleaned,
        "skipped": skipped,
        "errors": errors,
        "timeout_minutes": timeout_minutes or STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES,
    }
    logger.info("Stale online payment cleanup finished", extra=result)
    return result
