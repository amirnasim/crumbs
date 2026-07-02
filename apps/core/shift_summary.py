"""Daily shift summary — aggregate operational metrics for a selected date."""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal

from django.db.models import F, Q, Sum
from django.utils import timezone

from inventory.models import ProductInventory
from orders.models import Order, OrderItem
from payments.models import Payment

TOP_PRODUCTS_LIMIT = 10
LOW_STOCK_LIMIT = 20
PICKUP_LIST_LIMIT = 50
PAYMENT_ISSUES_LIMIT = 50

PAID_PAYMENT_STATUSES = (
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.CASH_RECEIVED,
    Order.PaymentStatus.COD_CONFIRMED,
)

PICKUP_READY_STATUSES = (Order.Status.PACKAGED,)
PICKUP_PENDING_STATUSES = (
    Order.Status.PAID,
    Order.Status.CONFIRMED_BY_SHOP,
    Order.Status.PREPARING,
)

PAYMENT_BREAKDOWN_METHODS = (
    Order.PaymentMethod.ONLINE,
    Order.PaymentMethod.COUNTER_CARD,
    Order.PaymentMethod.CASH,
)


@dataclass(frozen=True)
class PaymentBreakdownRow:
    method: str
    label: str
    count: int
    total: Decimal


@dataclass(frozen=True)
class TopProductRow:
    product_name: str
    product_id: int | None
    quantity_sold: int
    revenue: Decimal


@dataclass(frozen=True)
class ShiftSummary:
    selected_date: date
    total_sales: Decimal
    order_count: int
    paid_order_count: int
    awaiting_counter_payment_count: int
    cancelled_refunded_count: int
    payment_breakdown: tuple[PaymentBreakdownRow, ...]
    top_products: tuple[TopProductRow, ...]
    low_stock: tuple[ProductInventory, ...]
    ready_pickup_orders: tuple[Order, ...]
    pending_pickup_orders: tuple[Order, ...]
    payment_issues: tuple[Payment, ...]


def parse_shift_date(raw: str | None) -> date:
    if not raw:
        return timezone.localdate()
    return date.fromisoformat(raw)


def shift_datetime_range(selected_date: date) -> tuple[datetime, datetime]:
    tz = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(selected_date, time.min), tz)
    return start, start + timedelta(days=1)


def orders_for_shift_date(selected_date: date):
    start, end = shift_datetime_range(selected_date)
    return Order.objects.filter(created_at__gte=start, created_at__lt=end)


def paid_orders_for_shift(selected_date: date):
    return orders_for_shift_date(selected_date).filter(
        payment_status__in=PAID_PAYMENT_STATUSES,
    ).exclude(
        status__in=(Order.Status.CANCELLED, Order.Status.REFUNDED),
    )


def build_payment_breakdown(paid_orders) -> tuple[PaymentBreakdownRow, ...]:
    rows: list[PaymentBreakdownRow] = []
    for method in PAYMENT_BREAKDOWN_METHODS:
        method_orders = paid_orders.filter(payment_method=method)
        rows.append(
            PaymentBreakdownRow(
                method=method,
                label=dict(Order.PaymentMethod.choices).get(method, method),
                count=method_orders.count(),
                total=method_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00"),
            )
        )
    return tuple(rows)


def build_top_products(paid_orders, *, limit: int = TOP_PRODUCTS_LIMIT) -> tuple[TopProductRow, ...]:
    aggregates = (
        OrderItem.objects.filter(order__in=paid_orders)
        .values("product_id", "product_name")
        .annotate(
            quantity_sold=Sum("quantity"),
            revenue=Sum("line_total"),
        )
        .order_by("-quantity_sold", "product_name")[:limit]
    )
    return tuple(
        TopProductRow(
            product_name=row["product_name"],
            product_id=row["product_id"],
            quantity_sold=row["quantity_sold"] or 0,
            revenue=row["revenue"] or Decimal("0.00"),
        )
        for row in aggregates
    )


def low_stock_queryset(*, limit: int = LOW_STOCK_LIMIT):
    return (
        ProductInventory.objects.filter(track_stock=True)
        .filter(stock_quantity__lte=F("reserved_quantity") + F("low_stock_threshold"))
        .select_related("product")
        .order_by("stock_quantity", "product__name")[:limit]
    )


def payment_issues_for_shift(selected_date: date, *, limit: int = PAYMENT_ISSUES_LIMIT):
    start, end = shift_datetime_range(selected_date)
    return (
        Payment.objects.filter(order__created_at__gte=start, order__created_at__lt=end)
        .filter(
            Q(status=Payment.Status.FAILED)
            | Q(status__in=(Payment.Status.PENDING, Payment.Status.PROCESSING))
        )
        .select_related("order")
        .order_by("-created_at")[:limit]
    )


def build_shift_summary(selected_date: date) -> ShiftSummary:
    orders_qs = orders_for_shift_date(selected_date)
    paid_orders = paid_orders_for_shift(selected_date)

    total_sales = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")

    awaiting_counter = orders_qs.filter(
        status=Order.Status.AWAITING_PAYMENT,
        payment_method__in=(
            Order.PaymentMethod.CASH,
            Order.PaymentMethod.COUNTER_CARD,
        ),
    )

    cancelled_refunded = orders_qs.filter(
        Q(status__in=(Order.Status.CANCELLED, Order.Status.REFUNDED))
        | Q(payment_status=Order.PaymentStatus.REFUND_PROCESSED)
    )

    ready_pickup = list(
        orders_qs.filter(
            status__in=PICKUP_READY_STATUSES,
            payment_status__in=PAID_PAYMENT_STATUSES,
        ).order_by("created_at")[:PICKUP_LIST_LIMIT]
    )
    pending_pickup = list(
        orders_qs.filter(
            status__in=PICKUP_PENDING_STATUSES,
            payment_status__in=PAID_PAYMENT_STATUSES,
        ).order_by("created_at")[:PICKUP_LIST_LIMIT]
    )

    return ShiftSummary(
        selected_date=selected_date,
        total_sales=total_sales,
        order_count=orders_qs.count(),
        paid_order_count=paid_orders.count(),
        awaiting_counter_payment_count=awaiting_counter.count(),
        cancelled_refunded_count=cancelled_refunded.count(),
        payment_breakdown=build_payment_breakdown(paid_orders),
        top_products=build_top_products(paid_orders),
        low_stock=tuple(low_stock_queryset()),
        ready_pickup_orders=tuple(ready_pickup),
        pending_pickup_orders=tuple(pending_pickup),
        payment_issues=tuple(payment_issues_for_shift(selected_date)),
    )
