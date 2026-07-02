"""Shared pickup completion flow for staff screens."""

from orders.models import Order
from orders.services.order_service import OrderService


def complete_pickup_order(order: Order, *, actor: str) -> Order:
    previous_status = order.status
    if order.status == Order.Status.PACKAGED:
        OrderService.transition(
            order,
            Order.Status.OUT_FOR_DELIVERY,
            note="Pickup screen: ready for customer pickup",
            actor=actor,
        )
        order.refresh_from_db()
    order = OrderService.complete_delivery(order, actor=actor)
    if order.status == previous_status == Order.Status.DELIVERED:
        return order
    return order
