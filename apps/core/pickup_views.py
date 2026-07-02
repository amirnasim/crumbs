"""Staff pickup screen — packaged orders ready for customer collection."""

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from delivery.exceptions import InvalidTransitionError
from orders.exceptions import CheckoutError
from orders.models import Order
from orders.pickup_completion import complete_pickup_order

PICKUP_READY_PAYMENT_STATUSES = (
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.COD_CONFIRMED,
    Order.PaymentStatus.CASH_RECEIVED,
)

ACTION_MARK_PICKED_UP = "mark_picked_up"


def pickup_screen_queryset():
    return (
        Order.objects.filter(
            status=Order.Status.PACKAGED,
            payment_status__in=PICKUP_READY_PAYMENT_STATUSES,
        )
        .select_related("user")
        .prefetch_related("items")
        .order_by("created_at")
    )


@staff_member_required
def pickup_screen(request):
    orders = list(pickup_screen_queryset())
    context = {
        **admin.site.each_context(request),
        "title": "Pickup Screen",
        "ready_orders": orders,
        "counts": {"ready": len(orders)},
    }
    return render(request, "admin/pickup_screen.html", context)


@staff_member_required
@require_POST
def pickup_action(request):
    order_id = request.POST.get("order_id")
    action = request.POST.get("action", "")
    order = get_object_or_404(pickup_screen_queryset(), pk=order_id)
    actor = request.user.username

    if action != ACTION_MARK_PICKED_UP:
        messages.error(request, f"{order.order_number}: Unknown pickup action.")
        return redirect("admin:crumbs_pickup_screen")

    previous_status = order.status
    try:
        order = complete_pickup_order(order, actor=actor)
    except (InvalidTransitionError, CheckoutError) as exc:
        messages.error(request, f"{order.order_number}: {exc}")
        return redirect("admin:crumbs_pickup_screen")

    if order.status != previous_status:
        messages.success(request, f"{order.order_number}: marked as picked up.")
    else:
        messages.info(request, f"{order.order_number}: already picked up.")

    return redirect("admin:crumbs_pickup_screen")
