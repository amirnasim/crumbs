import secrets
from decimal import Decimal
from typing import NotRequired, TypedDict

from django.db import transaction
from django.utils import timezone

from cart.models import Cart
from cart.services import clear_cart
from products.services.stock_service import StockService
from products.models import Product

from ..exceptions import CheckoutError, EmptyCartError
from ..models import Order, OrderItem


class CustomerDetails(TypedDict):
    email: str
    first_name: str
    last_name: str
    phone: str
    address_line1: NotRequired[str]
    city: NotRequired[str]
    postal_code: NotRequired[str]
    address_line2: NotRequired[str]
    state: NotRequired[str]
    country: NotRequired[str]
    notes: NotRequired[str]
    payment_method: NotRequired[str]
    delivery_type: NotRequired[str]
    delivery_zone_id: NotRequired[int]
    delivery_fee: NotRequired[Decimal]


def generate_order_number() -> str:
    date_part = timezone.now().strftime("%Y%m%d")
    for _ in range(5):
        random_part = secrets.token_hex(3).upper()
        order_number = f"CR-{date_part}-{random_part}"
        if not Order.objects.filter(order_number=order_number).exists():
            return order_number
    raise CheckoutError("Unable to generate a unique order number.")


def _validate_cart_items(cart_items: list) -> list:
    if not cart_items:
        raise EmptyCartError("Cannot checkout an empty cart.")

    unavailable = [item.product.name for item in cart_items if not item.product.is_available]
    if unavailable:
        raise CheckoutError(
            "Some items are no longer available: " + ", ".join(unavailable)
        )

    for item in cart_items:
        try:
            StockService.check_availability(item.product, item.quantity)
        except Exception as exc:
            raise CheckoutError(str(exc)) from exc

    return cart_items


def _validate_cart(cart: Cart) -> list:
    items = list(cart.items.select_related("product"))
    return _validate_cart_items(items)


def _normalize_fulfillment_details(
    customer: CustomerDetails,
    *,
    delivery_type: str,
    delivery_fee: Decimal,
    delivery_zone_id: int | None,
) -> tuple[str, Decimal, int | None, dict[str, str]]:
    address_fields = {
        "address_line1": customer.get("address_line1", ""),
        "address_line2": customer.get("address_line2", ""),
        "city": customer.get("city", ""),
        "state": customer.get("state", ""),
        "postal_code": customer.get("postal_code", ""),
        "country": customer.get("country", "Iran") or "Iran",
    }

    if delivery_type == Order.FulfillmentType.PICKUP:
        delivery_zone_id = None
        delivery_fee = Decimal("0.00")
        address_fields = {
            "address_line1": "",
            "address_line2": "",
            "city": "",
            "state": "",
            "postal_code": "",
            "country": "Iran",
        }

    return delivery_type, delivery_fee, delivery_zone_id, address_fields


@transaction.atomic
def create_order_from_cart(
    cart: Cart,
    customer: CustomerDetails,
    *,
    user=None,
    cart_items=None,
    initial_status: str | None = None,
    initial_payment_status: str | None = None,
) -> Order:
    if cart_items is None:
        from cart.services import lock_cart_for_checkout

        cart, cart_items = lock_cart_for_checkout(cart)

    cart_items = _validate_cart_items(cart_items)

    payment_method = customer.get("payment_method", Order.PaymentMethod.ONLINE)
    delivery_type = customer.get("delivery_type", Order.FulfillmentType.PICKUP)
    delivery_fee = Decimal(customer.get("delivery_fee", "0.00"))
    delivery_zone_id = customer.get("delivery_zone_id")
    delivery_type, delivery_fee, delivery_zone_id, address_fields = _normalize_fulfillment_details(
        customer,
        delivery_type=delivery_type,
        delivery_fee=delivery_fee,
        delivery_zone_id=delivery_zone_id,
    )

    subtotal = Decimal("0.00")
    order = Order.objects.create(
        order_number=generate_order_number(),
        user=user or cart.user,
        email=customer["email"],
        phone=customer["phone"],
        first_name=customer["first_name"],
        last_name=customer["last_name"],
        notes=customer.get("notes", ""),
        payment_method=payment_method,
        delivery_type=delivery_type,
        delivery_zone_id=delivery_zone_id,
        delivery_fee=delivery_fee,
        subtotal=Decimal("0.00"),
        total=Decimal("0.00"),
        status=initial_status or Order.Status.PENDING_PAYMENT,
        payment_status=initial_payment_status or Order.PaymentStatus.PENDING_PAYMENT,
        **address_fields,
    )

    order_items = []
    for item in cart_items:
        line_total = item.product.price * item.quantity
        subtotal += line_total
        order_items.append(
            OrderItem(
                order=order,
                product=item.product,
                product_name=item.product.name,
                unit_price=item.product.price,
                quantity=item.quantity,
                line_total=line_total,
            )
        )

    OrderItem.objects.bulk_create(order_items)

    order.subtotal = subtotal
    order.total = subtotal + delivery_fee
    order.save(update_fields=["subtotal", "total", "updated_at"])

    from orders.daily_sequence import assign_daily_sequence

    assign_daily_sequence(order)

    return order


@transaction.atomic
def finalize_checkout_stock(cart: Cart, order: Order) -> None:
    """Move stock holds from cart to order, then clear cart line items."""
    StockService.release_cart_reservations(cart)
    StockService.reserve_for_order(order)
    clear_cart(cart)
