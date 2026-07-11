from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db import transaction

from orders.models import Order
from products.models import Product
from products.services.stock_service import StockService

from .exceptions import (
    CartMutationBlocked,
    InvalidQuantityError,
    ProductUnavailableError,
)
from .models import Cart, CartItem

User = get_user_model()

_IN_PROGRESS_ORDER_STATUSES = {
    Order.Status.PENDING_PAYMENT,
    Order.Status.PAID,
    Order.Status.CONFIRMED_BY_SHOP,
}
_TERMINAL_PAYMENT_STATUSES = {
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.CASH_RECEIVED,
    Order.PaymentStatus.FAILED,
    Order.PaymentStatus.REFUND_PROCESSED,
}


def is_order_checkout_in_progress(order: Order | None) -> bool:
    if order is None:
        return False
    if order.status == Order.Status.CANCELLED:
        return False
    if order.payment_status in _TERMINAL_PAYMENT_STATUSES:
        return False
    return order.status in _IN_PROGRESS_ORDER_STATUSES


def lock_cart_for_checkout(cart: Cart) -> tuple[Cart, list[CartItem]]:
    """Lock cart row and all cart items for checkout."""
    cart = Cart.objects.select_for_update().get(pk=cart.pk)
    cart_items = list(
        CartItem.objects.select_for_update()
        .filter(cart=cart)
        .select_related("product")
        .order_by("pk")
    )
    return cart, cart_items


def calculate_subtotal(cart_items: list[CartItem]) -> Decimal:
    total = Decimal("0.00")
    for item in cart_items:
        total += item.product.price * item.quantity
    return total


def set_active_checkout_order(cart: Cart, order: Order) -> None:
    cart.active_checkout_order = order
    cart.save(update_fields=["active_checkout_order", "updated_at"])


def clear_active_checkout_order(cart: Cart) -> None:
    if cart.active_checkout_order_id is None:
        return
    cart.active_checkout_order = None
    cart.save(update_fields=["active_checkout_order", "updated_at"])


def ensure_cart_mutable(cart: Cart) -> None:
    """Reject cart mutations while a checkout is in progress."""
    if not cart.active_checkout_order_id:
        return

    order = cart.active_checkout_order
    if is_order_checkout_in_progress(order):
        raise CartMutationBlocked("Cart cannot be modified while checkout is in progress.")


def get_or_create_cart(*, user=None, session_key=None) -> tuple[Cart, bool]:
    if user is not None:
        return Cart.objects.get_or_create(user=user)

    if not session_key:
        raise ValueError("Either user or session_key is required.")

    return Cart.objects.get_or_create(session_key=session_key)


def _validate_quantity(quantity: int) -> None:
    if quantity < 1:
        raise InvalidQuantityError("Quantity must be at least 1.")


def _validate_product(product: Product, quantity: int = 1, *, cart: Cart | None = None) -> None:
    if not product.is_available:
        raise ProductUnavailableError(f"{product.name} is not available.")
    StockService.check_availability(product, quantity, cart=cart)


@transaction.atomic
def add_item(cart: Cart, product: Product, quantity: int = 1) -> CartItem:
    ensure_cart_mutable(cart)
    _validate_quantity(quantity)

    item = CartItem.objects.filter(cart=cart, product=product).first()
    new_quantity = quantity if item is None else item.quantity + quantity
    _validate_product(product, new_quantity, cart=cart)

    item, created = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )
    if not created:
        item.quantity += quantity
        item.save(update_fields=["quantity", "updated_at"])
    StockService.reserve_for_cart_item(cart, product, item.quantity)
    return item


@transaction.atomic
def set_item_quantity(cart: Cart, product: Product, quantity: int) -> CartItem | None:
    ensure_cart_mutable(cart)
    _validate_quantity(quantity)
    _validate_product(product, quantity, cart=cart)

    item, _ = CartItem.objects.get_or_create(
        cart=cart,
        product=product,
        defaults={"quantity": quantity},
    )
    item.quantity = quantity
    item.save(update_fields=["quantity", "updated_at"])
    StockService.reserve_for_cart_item(cart, product, item.quantity)
    return item


def remove_item(cart: Cart, product: Product) -> None:
    ensure_cart_mutable(cart)
    StockService.release_cart_reservations_for_product(cart, product)
    CartItem.objects.filter(cart=cart, product=product).delete()


def clear_cart(cart: Cart) -> None:
    StockService.release_cart_reservations(cart)
    cart.items.all().delete()


@transaction.atomic
def merge_carts(source: Cart, target: Cart) -> Cart:
    """Merge a session cart into a user's cart (e.g. after login)."""
    if source.pk == target.pk:
        return target

    for item in source.items.select_related("product"):
        if item.product.is_available:
            add_item(target, item.product, item.quantity)

    source.delete()
    return target