"""Daily short order number allocation — sequential per local calendar day."""

from django.db import IntegrityError, transaction
from django.db.models import Max
from django.utils import timezone

from orders.exceptions import CheckoutError
from orders.models import Order

DAILY_SEQUENCE_START = 101
MAX_ALLOCATION_RETRIES = 5


def local_order_date(order: Order):
    return timezone.localdate(order.created_at)


def format_display_number(sequence: int | None) -> str:
    if not sequence:
        return ""
    return f"#{sequence}"


@transaction.atomic
def assign_daily_sequence(order: Order) -> Order:
    """Assign the next daily sequence number for the order's local created date."""
    if order.daily_sequence:
        return order

    local_date = local_order_date(order)

    for _attempt in range(MAX_ALLOCATION_RETRIES):
        order.refresh_from_db()
        if order.daily_sequence:
            return order

        Order.objects.filter(daily_sequence_date=local_date).select_for_update().exists()

        max_sequence = (
            Order.objects.filter(
                daily_sequence_date=local_date,
                daily_sequence__isnull=False,
            ).aggregate(max_sequence=Max("daily_sequence"))["max_sequence"]
        )
        next_sequence = (max_sequence or (DAILY_SEQUENCE_START - 1)) + 1

        order.daily_sequence = next_sequence
        order.daily_sequence_date = local_date
        try:
            order.save(update_fields=["daily_sequence", "daily_sequence_date", "updated_at"])
        except IntegrityError:
            continue
        return order

    raise CheckoutError("Unable to assign a daily order number.")
