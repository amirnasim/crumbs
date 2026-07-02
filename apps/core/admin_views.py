from django.conf import settings
from django.contrib import admin
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import F, Q, Sum
from django.shortcuts import render
from django.utils import timezone

from core.models import BackgroundTaskLog
from inventory.models import ProductInventory
from orders.models import Order
from payments.models import Payment
from payments.stale_cleanup import get_stale_online_payment_cutoff
from products.models import Product

DASHBOARD_LIMIT = 50
ZARINPAL_MERCHANT_ID_LENGTH = 36

NEW_ORDER_STATUSES = (
    Order.Status.PENDING_PAYMENT,
    Order.Status.CONFIRMED_BY_SHOP,
)

ORDERS_IN_PREPARATION_STATUSES = (
    Order.Status.CONFIRMED_BY_SHOP,
    Order.Status.PREPARING,
    Order.Status.PACKAGED,
)

FAILED_TASK_STATUSES = (
    BackgroundTaskLog.Status.FAILURE,
    BackgroundTaskLog.Status.RETRY,
    BackgroundTaskLog.Status.DEAD,
)


def _legacy_cod_pending_queryset():
    return (
        Order.objects.filter(
            payment_method=Order.PaymentMethod.COD,
            payment_status=Order.PaymentStatus.COD_PENDING,
        )
        .exclude(status__in=(Order.Status.CANCELLED, Order.Status.REFUNDED))
        .order_by("created_at")
    )


def _awaiting_counter_payment_queryset():
    return (
        Order.objects.filter(
            status=Order.Status.AWAITING_PAYMENT,
            payment_method__in=(
                Order.PaymentMethod.CASH,
                Order.PaymentMethod.COUNTER_CARD,
            ),
        )
        .exclude(payment_status=Order.PaymentStatus.PAID)
        .order_by("created_at")
    )


@staff_member_required
def operations_dashboard(request):
    new_orders = (
        Order.objects.filter(status__in=NEW_ORDER_STATUSES)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )

    legacy_cod_to_collect = _legacy_cod_pending_queryset()[:DASHBOARD_LIMIT]
    awaiting_counter_payment = _awaiting_counter_payment_queryset()[:DASHBOARD_LIMIT]

    orders_in_preparation = (
        Order.objects.filter(status__in=ORDERS_IN_PREPARATION_STATUSES)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )

    low_stock = (
        ProductInventory.objects.filter(track_stock=True)
        .filter(stock_quantity__lte=F("reserved_quantity") + F("low_stock_threshold"))
        .select_related("product")
        .order_by("stock_quantity", "product__name")
        [:DASHBOARD_LIMIT]
    )

    failed_tasks = (
        BackgroundTaskLog.objects.filter(status__in=FAILED_TASK_STATUSES)
        .order_by("-created_at")
        [:DASHBOARD_LIMIT]
    )

    stale_cutoff = get_stale_online_payment_cutoff()
    payment_issues = (
        Payment.objects.filter(
            Q(status=Payment.Status.FAILED)
            | Q(
                status=Payment.Status.PENDING,
                provider__in=(Payment.Provider.ZARINPAL, Payment.Provider.STRIPE),
                created_at__lt=stale_cutoff,
            )
        )
        .select_related("order")
        .order_by("-created_at")
        [:DASHBOARD_LIMIT]
    )

    inactive_products = (
        Product.objects.exclude(availability_status=Product.AvailabilityStatus.AVAILABLE)
        .select_related("category")
        .order_by("name")
        [:DASHBOARD_LIMIT]
    )
    products_without_inventory = (
        Product.objects.filter(inventory__isnull=True)
        .select_related("category")
        .order_by("name")
        [:DASHBOARD_LIMIT]
    )
    invalid_price_products = (
        Product.objects.filter(price__lte=0)
        .select_related("category")
        .order_by("name")
        [:DASHBOARD_LIMIT]
    )
    products_missing_category = (
        Product.objects.filter(category__isnull=True)
        .order_by("name")
        [:DASHBOARD_LIMIT]
    )

    context = {
        **admin.site.each_context(request),
        "title": "Operations Dashboard",
        "new_orders": new_orders,
        "legacy_cod_to_collect": legacy_cod_to_collect,
        "awaiting_counter_payment": awaiting_counter_payment,
        "orders_in_preparation": orders_in_preparation,
        "low_stock": low_stock,
        "failed_tasks": failed_tasks,
        "payment_issues": payment_issues,
        "inactive_products": inactive_products,
        "products_without_inventory": products_without_inventory,
        "invalid_price_products": invalid_price_products,
        "products_missing_category": products_missing_category,
        "counts": {
            "new_orders": new_orders.count(),
            "legacy_cod_to_collect": legacy_cod_to_collect.count(),
            "awaiting_counter_payment": awaiting_counter_payment.count(),
            "orders_in_preparation": orders_in_preparation.count(),
            "low_stock": low_stock.count(),
            "failed_tasks": failed_tasks.count(),
            "payment_issues": payment_issues.count(),
            "inactive_products": inactive_products.count(),
            "products_without_inventory": products_without_inventory.count(),
            "invalid_price_products": invalid_price_products.count(),
            "products_missing_category": products_missing_category.count(),
        },
    }
    return render(request, "admin/operations_dashboard.html", context)


def build_zarinpal_setup_status() -> dict:
    merchant_id = (settings.ZARINPAL_MERCHANT_ID or "").strip()
    callback_url = (settings.ZARINPAL_CALLBACK_URL or settings.PAYMENT_SUCCESS_URL or "").strip()
    provider = settings.DEFAULT_PAYMENT_PROVIDER
    online_enabled = settings.DEFAULT_PAYMENT_METHOD == Order.PaymentMethod.ONLINE

    return {
        "default_payment_provider": provider,
        "zarinpal_sandbox": settings.ZARINPAL_SANDBOX,
        "merchant_id_exists": bool(merchant_id),
        "merchant_id_valid_length": len(merchant_id) == ZARINPAL_MERCHANT_ID_LENGTH,
        "callback_url": callback_url or "—",
        "online_payment_enabled": online_enabled,
        "ready_for_sandbox_test": (
            provider == Payment.Provider.ZARINPAL
            and bool(merchant_id)
            and len(merchant_id) == ZARINPAL_MERCHANT_ID_LENGTH
            and bool(callback_url)
            and online_enabled
        ),
    }


@staff_member_required
def ops_dashboard(request):
    low_stock = (
        ProductInventory.objects.filter(track_stock=True)
        .filter(stock_quantity__lte=F("reserved_quantity") + F("low_stock_threshold"))
        .select_related("product")
        .order_by("stock_quantity", "product__name")
        [:DASHBOARD_LIMIT]
    )
    out_of_stock = (
        ProductInventory.objects.filter(track_stock=True)
        .filter(stock_quantity__lte=F("reserved_quantity"))
        .select_related("product")
        .order_by("product__name")
        [:DASHBOARD_LIMIT]
    )
    products_without_inventory = (
        Product.objects.filter(inventory__isnull=True)
        .select_related("category")
        .order_by("name")
        [:DASHBOARD_LIMIT]
    )
    reserved_rows = (
        ProductInventory.objects.filter(track_stock=True, reserved_quantity__gt=0)
        .select_related("product")
        .order_by("-reserved_quantity", "product__name")
        [:DASHBOARD_LIMIT]
    )
    reserved_totals = ProductInventory.objects.filter(track_stock=True).aggregate(
        total_stock=Sum("stock_quantity"),
        total_reserved=Sum("reserved_quantity"),
    )

    new_orders = (
        Order.objects.filter(status=Order.Status.PENDING_PAYMENT)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )
    confirmed_orders = (
        Order.objects.filter(status=Order.Status.CONFIRMED_BY_SHOP)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )
    preparing_orders = (
        Order.objects.filter(status=Order.Status.PREPARING)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )
    ready_for_pickup_orders = (
        Order.objects.filter(status=Order.Status.PACKAGED)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )
    delivered_pending_finalization = (
        Order.objects.filter(status=Order.Status.DELIVERED)
        .exclude(
            payment_status__in=(
                Order.PaymentStatus.PAID,
                Order.PaymentStatus.CASH_RECEIVED,
                Order.PaymentStatus.REFUND_PROCESSED,
            )
        )
        .order_by("-updated_at")
        [:DASHBOARD_LIMIT]
    )

    legacy_cod_pending_collection = _legacy_cod_pending_queryset()[:DASHBOARD_LIMIT]
    awaiting_counter_payment = _awaiting_counter_payment_queryset()[:DASHBOARD_LIMIT]
    legacy_out_for_delivery_orders = (
        Order.objects.filter(status=Order.Status.OUT_FOR_DELIVERY)
        .order_by("created_at")
        [:DASHBOARD_LIMIT]
    )
    failed_payments = (
        Payment.objects.filter(status=Payment.Status.FAILED)
        .select_related("order")
        .order_by("-created_at")
        [:DASHBOARD_LIMIT]
    )
    stale_cutoff = get_stale_online_payment_cutoff()
    stale_online_payments = (
        Payment.objects.filter(
            status__in=(Payment.Status.PENDING, Payment.Status.PROCESSING),
            provider__in=(Payment.Provider.ZARINPAL, Payment.Provider.STRIPE),
            created_at__lt=stale_cutoff,
        )
        .select_related("order")
        .order_by("-created_at")
        [:DASHBOARD_LIMIT]
    )
    order_paid_payment_pending = (
        Order.objects.filter(payment_status=Order.PaymentStatus.PAID)
        .filter(
            payments__status__in=(Payment.Status.PENDING, Payment.Status.PROCESSING),
        )
        .distinct()
        .order_by("-updated_at")
        [:DASHBOARD_LIMIT]
    )
    cash_received_payment_pending = (
        Order.objects.filter(payment_status=Order.PaymentStatus.CASH_RECEIVED)
        .filter(payments__status=Payment.Status.PENDING)
        .distinct()
        .order_by("-updated_at")
        [:DASHBOARD_LIMIT]
    )

    zarinpal_status = build_zarinpal_setup_status()

    legacy_cod_count = legacy_cod_pending_collection.count()
    legacy_in_transit_count = legacy_out_for_delivery_orders.count()
    show_legacy_delivery_section = legacy_cod_count > 0 or legacy_in_transit_count > 0

    context = {
        **admin.site.each_context(request),
        "title": "Operations Task Center",
        "low_stock": low_stock,
        "out_of_stock": out_of_stock,
        "products_without_inventory": products_without_inventory,
        "reserved_rows": reserved_rows,
        "reserved_totals": reserved_totals,
        "new_orders": new_orders,
        "confirmed_orders": confirmed_orders,
        "preparing_orders": preparing_orders,
        "ready_for_pickup_orders": ready_for_pickup_orders,
        "delivered_pending_finalization": delivered_pending_finalization,
        "legacy_cod_pending_collection": legacy_cod_pending_collection,
        "awaiting_counter_payment": awaiting_counter_payment,
        "legacy_out_for_delivery_orders": legacy_out_for_delivery_orders,
        "failed_payments": failed_payments,
        "stale_online_payments": stale_online_payments,
        "order_paid_payment_pending": order_paid_payment_pending,
        "cash_received_payment_pending": cash_received_payment_pending,
        "zarinpal_status": zarinpal_status,
        "show_legacy_delivery_section": show_legacy_delivery_section,
        "counts": {
            "low_stock": low_stock.count(),
            "out_of_stock": out_of_stock.count(),
            "products_without_inventory": products_without_inventory.count(),
            "reserved_rows": reserved_rows.count(),
            "new_orders": new_orders.count(),
            "confirmed_orders": confirmed_orders.count(),
            "preparing_orders": preparing_orders.count(),
            "ready_for_pickup_orders": ready_for_pickup_orders.count(),
            "delivered_pending_finalization": delivered_pending_finalization.count(),
            "legacy_cod_pending_collection": legacy_cod_pending_collection.count(),
            "awaiting_counter_payment": awaiting_counter_payment.count(),
            "legacy_out_for_delivery_orders": legacy_out_for_delivery_orders.count(),
            "failed_payments": failed_payments.count(),
            "stale_online_payments": stale_online_payments.count(),
            "order_paid_payment_pending": order_paid_payment_pending.count(),
            "cash_received_payment_pending": cash_received_payment_pending.count(),
        },
    }
    return render(request, "admin/ops_dashboard.html", context)
