"""Checkout session helpers for guest order confirmation access."""

SESSION_CHECKOUT_ORDER_ACCESS = "checkout_order_access"


def grant_checkout_order_access(request, order_number: str) -> None:
    allowed = list(request.session.get(SESSION_CHECKOUT_ORDER_ACCESS, []))
    if order_number not in allowed:
        allowed.append(order_number)
    request.session[SESSION_CHECKOUT_ORDER_ACCESS] = allowed[-10:]
    request.session.modified = True


def can_view_checkout_order(request, order) -> bool:
    if request.user.is_staff:
        return True
    if request.user.is_authenticated and order.user_id == request.user.id:
        return True
    allowed = request.session.get(SESSION_CHECKOUT_ORDER_ACCESS, [])
    return order.order_number in allowed
