"""Staff order quick lookup — search and recent active orders."""

from django.db.models import Q, QuerySet

from core.kitchen_views import KITCHEN_PAYMENT_STATUSES, KITCHEN_QUEUE_STATUSES
from core.pickup_views import PICKUP_READY_PAYMENT_STATUSES
from orders.models import Order

DEFAULT_LOOKUP_LIMIT = 20
SEARCH_LOOKUP_LIMIT = 50

INACTIVE_ORDER_STATUSES = (
    Order.Status.DELIVERED,
    Order.Status.CANCELLED,
    Order.Status.REFUNDED,
)

KITCHEN_EXCLUDED_PAYMENT_STATUSES = (
    Order.PaymentStatus.PENDING_PAYMENT,
    Order.PaymentStatus.FAILED,
    Order.PaymentStatus.COD_PENDING,
)


def lookup_queryset() -> QuerySet[Order]:
    return Order.objects.all()


def recent_active_orders_queryset(*, limit: int = DEFAULT_LOOKUP_LIMIT) -> QuerySet[Order]:
    return (
        lookup_queryset()
        .exclude(status__in=INACTIVE_ORDER_STATUSES)
        .order_by("-created_at")[:limit]
    )


def search_orders_queryset(query: str, *, limit: int = SEARCH_LOOKUP_LIMIT) -> QuerySet[Order]:
    term = (query or "").strip()
    if not term:
        return recent_active_orders_queryset(limit=min(limit, DEFAULT_LOOKUP_LIMIT))

    filters = (
        Q(order_number__icontains=term)
        | Q(phone__icontains=term)
        | Q(first_name__icontains=term)
        | Q(last_name__icontains=term)
        | Q(notes__icontains=term)
    )
    if term.isdigit():
        filters |= Q(daily_sequence=int(term))
    return lookup_queryset().filter(filters).order_by("-created_at")[:limit]


def order_is_kitchen_relevant(order: Order) -> bool:
    if order.status not in KITCHEN_QUEUE_STATUSES:
        return False
    if order.payment_status not in KITCHEN_PAYMENT_STATUSES:
        return False
    return order.payment_status not in KITCHEN_EXCLUDED_PAYMENT_STATUSES


def order_is_pickup_relevant(order: Order) -> bool:
    return (
        order.status == Order.Status.PACKAGED
        and order.payment_status in PICKUP_READY_PAYMENT_STATUSES
    )
