"""
Iran-realistic order state machine.

All order status changes MUST go through OrderService.transition().
"""

from orders.models import Order

ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    Order.Status.PENDING_PAYMENT: {
        Order.Status.PAID,
        Order.Status.CONFIRMED_BY_SHOP,
        Order.Status.CANCELLED,
    },
    Order.Status.AWAITING_PAYMENT: {
        Order.Status.PREPARING,
        Order.Status.CANCELLED,
    },
    Order.Status.PAID: {
        Order.Status.CONFIRMED_BY_SHOP,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    },
    Order.Status.CONFIRMED_BY_SHOP: {
        Order.Status.PREPARING,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    },
    Order.Status.PREPARING: {
        Order.Status.PACKAGED,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    },
    Order.Status.PACKAGED: {
        Order.Status.OUT_FOR_DELIVERY,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    },
    Order.Status.OUT_FOR_DELIVERY: {
        Order.Status.DELIVERED,
        Order.Status.CANCELLED,
        Order.Status.REFUNDED,
    },
    Order.Status.DELIVERED: {
        Order.Status.REFUNDED,
    },
    Order.Status.CANCELLED: set(),
    Order.Status.REFUNDED: set(),
}

TERMINAL_STATUSES = {
    Order.Status.CANCELLED,
    Order.Status.REFUNDED,
    Order.Status.DELIVERED,
}

STATUS_TO_SMS_EVENT: dict[str, str] = {
    Order.Status.AWAITING_PAYMENT: "order_created",
    Order.Status.CONFIRMED_BY_SHOP: "order_confirmed_by_shop",
    Order.Status.PREPARING: "order_preparing",
    Order.Status.PACKAGED: "order_packaged",
    Order.Status.OUT_FOR_DELIVERY: "order_out_for_delivery",
    Order.Status.DELIVERED: "delivered",
    Order.Status.CANCELLED: "order_cancelled",
    Order.Status.REFUNDED: "refund_processed",
}

STATUS_LABELS_FA = {
    Order.Status.PENDING_PAYMENT: "در انتظار پرداخت",
    Order.Status.AWAITING_PAYMENT: "در انتظار پرداخت در صندوق",
    Order.Status.PAID: "پرداخت شده",
    Order.Status.CONFIRMED_BY_SHOP: "تأیید فروشگاه",
    Order.Status.PREPARING: "در حال آماده‌سازی",
    Order.Status.PACKAGED: "بسته‌بندی شد",
    Order.Status.OUT_FOR_DELIVERY: "در مسیر تحویل",
    Order.Status.DELIVERED: "تحویل داده شد",
    Order.Status.CANCELLED: "لغو شد",
    Order.Status.REFUNDED: "استرداد شد",
}


def can_transition(order: Order, new_status: str) -> bool:
    if order.status == new_status:
        return True
    return new_status in ALLOWED_TRANSITIONS.get(order.status, set())


def validate_transition(order: Order, new_status: str) -> None:
    from delivery.exceptions import InvalidTransitionError

    if not can_transition(order, new_status):
        raise InvalidTransitionError(
            f"Cannot transition order {order.order_number} from "
            f"'{order.status}' to '{new_status}'."
        )
