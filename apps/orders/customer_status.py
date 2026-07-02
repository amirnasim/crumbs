"""Customer-facing order status timeline for in-cafe pickup orders."""

from dataclasses import dataclass

from orders.models import Order

TIMELINE_STEP_AWAITING_PAYMENT = "awaiting_payment"
TIMELINE_STEP_PREPARING = "preparing"
TIMELINE_STEP_READY = "ready"
TIMELINE_STEP_DELIVERED = "delivered"

CUSTOMER_TIMELINE_STEPS: tuple[tuple[str, str], ...] = (
    (TIMELINE_STEP_AWAITING_PAYMENT, "در انتظار پرداخت"),
    (TIMELINE_STEP_PREPARING, "در حال آماده‌سازی"),
    (TIMELINE_STEP_READY, "آماده تحویل از کانتر"),
    (TIMELINE_STEP_DELIVERED, "تحویل شد"),
)

COUNTER_AWAITING_PAYMENT_MESSAGE = "لطفاً برای نهایی شدن سفارش به صندوق مراجعه کنید."
PACKAGED_READY_MESSAGE = "سفارش شما آماده تحویل از کانتر است."


@dataclass(frozen=True)
class TimelineStep:
    key: str
    label: str
    state: str


@dataclass(frozen=True)
class OrderStatusTimeline:
    steps: tuple[TimelineStep, ...]
    banner: str
    current_key: str | None


def map_order_status_to_timeline_key(status: str) -> str | None:
    if status in {Order.Status.AWAITING_PAYMENT, Order.Status.PENDING_PAYMENT}:
        return TIMELINE_STEP_AWAITING_PAYMENT
    if status in {
        Order.Status.PAID,
        Order.Status.CONFIRMED_BY_SHOP,
        Order.Status.PREPARING,
    }:
        return TIMELINE_STEP_PREPARING
    if status == Order.Status.PACKAGED:
        return TIMELINE_STEP_READY
    if status == Order.Status.DELIVERED:
        return TIMELINE_STEP_DELIVERED
    return None


def build_order_status_timeline(order: Order) -> OrderStatusTimeline:
    current_key = map_order_status_to_timeline_key(order.status)
    step_keys = [key for key, _ in CUSTOMER_TIMELINE_STEPS]
    steps: list[TimelineStep] = []

    if current_key is None:
        for key, label in CUSTOMER_TIMELINE_STEPS:
            steps.append(TimelineStep(key=key, label=label, state="upcoming"))
    else:
        current_index = step_keys.index(current_key)
        for index, (key, label) in enumerate(CUSTOMER_TIMELINE_STEPS):
            if index < current_index:
                state = "complete"
            elif index == current_index:
                state = "current"
            else:
                state = "upcoming"
            steps.append(TimelineStep(key=key, label=label, state=state))

    banner = ""
    if order.status == Order.Status.AWAITING_PAYMENT and order.is_counter_payment:
        banner = COUNTER_AWAITING_PAYMENT_MESSAGE
    elif order.status == Order.Status.PACKAGED:
        banner = PACKAGED_READY_MESSAGE

    return OrderStatusTimeline(steps=tuple(steps), banner=banner, current_key=current_key)
