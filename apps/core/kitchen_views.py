"""Staff kitchen queue — in-cafe order preparation screen."""

from django.contrib import admin, messages
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_POST

from delivery.exceptions import InvalidTransitionError
from orders.exceptions import CheckoutError
from orders.models import Order
from orders.services.order_service import OrderService

KITCHEN_QUEUE_STATUSES = (
    Order.Status.PAID,
    Order.Status.CONFIRMED_BY_SHOP,
    Order.Status.PREPARING,
    Order.Status.PACKAGED,
)

KITCHEN_PAYMENT_STATUSES = (
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.COD_CONFIRMED,
    Order.PaymentStatus.CASH_RECEIVED,
)

ACTION_START_PREPARING = "start_preparing"
ACTION_MARK_READY = "mark_ready"
ACTION_MARK_COMPLETED = "mark_completed"


def kitchen_order_queryset():
    """Active in-cafe pickup orders for the kitchen screen."""
    return (
        Order.objects.filter(
            status__in=KITCHEN_QUEUE_STATUSES,
            payment_status__in=KITCHEN_PAYMENT_STATUSES,
        )
        .exclude(
            payment_status__in=(
                Order.PaymentStatus.PENDING_PAYMENT,
                Order.PaymentStatus.FAILED,
                Order.PaymentStatus.COD_PENDING,
            )
        )
        .select_related("user")
        .prefetch_related("items")
        .order_by("created_at")
    )


def _partition_kitchen_orders(orders):
    waiting = []
    preparing = []
    ready = []
    for order in orders:
        if order.status in {Order.Status.PAID, Order.Status.CONFIRMED_BY_SHOP}:
            waiting.append(order)
        elif order.status == Order.Status.PREPARING:
            preparing.append(order)
        elif order.status == Order.Status.PACKAGED:
            ready.append(order)
    return waiting, preparing, ready


def _start_preparing(order: Order, *, actor: str) -> Order:
    if order.status == Order.Status.PREPARING:
        return order
    if order.status == Order.Status.PAID:
        OrderService.transition(
            order,
            Order.Status.CONFIRMED_BY_SHOP,
            note="Kitchen queue: confirmed for preparation",
            actor=actor,
        )
        order.refresh_from_db()
    if order.status == Order.Status.CONFIRMED_BY_SHOP:
        return OrderService.transition(
            order,
            Order.Status.PREPARING,
            note="Kitchen queue: started preparing",
            actor=actor,
        )
    raise InvalidTransitionError(
        f"Cannot start preparing order {order.order_number} from status '{order.status}'."
    )


def _mark_ready(order: Order, *, actor: str) -> Order:
    return OrderService.transition(
        order,
        Order.Status.PACKAGED,
        note="Kitchen queue: ready for pickup",
        actor=actor,
    )


from orders.pickup_completion import complete_pickup_order


def _apply_kitchen_action(order: Order, action: str, *, actor: str) -> tuple[Order, bool]:
    """Return (order, changed)."""
    previous_status = order.status
    if action == ACTION_START_PREPARING:
        order = _start_preparing(order, actor=actor)
    elif action == ACTION_MARK_READY:
        order = _mark_ready(order, actor=actor)
    elif action == ACTION_MARK_COMPLETED:
        order = complete_pickup_order(order, actor=actor)
    else:
        raise ValueError(f"Unknown kitchen action: {action}")
    return order, order.status != previous_status


@staff_member_required
def kitchen_queue(request):
    orders = list(kitchen_order_queryset())
    waiting, preparing, ready = _partition_kitchen_orders(orders)
    context = {
        **admin.site.each_context(request),
        "title": "Kitchen Queue",
        "waiting_orders": waiting,
        "preparing_orders": preparing,
        "ready_orders": ready,
        "counts": {
            "waiting": len(waiting),
            "preparing": len(preparing),
            "ready": len(ready),
            "total": len(orders),
        },
    }
    return render(request, "admin/kitchen_queue.html", context)


@staff_member_required
@require_POST
def kitchen_action(request):
    order_id = request.POST.get("order_id")
    action = request.POST.get("action", "")
    order = get_object_or_404(kitchen_order_queryset(), pk=order_id)
    actor = request.user.username

    try:
        order, changed = _apply_kitchen_action(order, action, actor=actor)
    except (InvalidTransitionError, CheckoutError, ValueError) as exc:
        messages.error(request, f"{order.order_number}: {exc}")
        return redirect("admin:crumbs_kitchen")

    if changed:
        messages.success(request, f"{order.order_number}: updated to {order.get_status_display()}.")
    else:
        messages.info(request, f"{order.order_number}: already {order.get_status_display()}.")

    return redirect("admin:crumbs_kitchen")
