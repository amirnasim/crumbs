import logging
from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db import transaction

from cart import services as cart_services
from cart.exceptions import CheckoutAlreadyInProgress
from delivery.exceptions import MinimumOrderError, UndeliverableAddressError
from delivery.models import DeliveryZone
from orders.exceptions import CheckoutError, EmptyCartError
from orders.models import Order
from orders.services import create_order_from_cart, finalize_checkout_stock
from orders.services.order_service import OrderService
from payments.exceptions import PaymentError
from payments.services import PaymentService

logger = logging.getLogger(__name__)

ONLINE_PAYMENT_UNAVAILABLE_MESSAGE = (
    "پرداخت آنلاین در حال حاضر در دسترس نیست. "
    "لطفاً چند دقیقه دیگر دوباره تلاش کنید."
)


def _normalize(value: str) -> str:
    return value.strip().casefold()


class DeliveryService:
    """Delivery zone resolution and fee calculation — legacy delivery orders only."""

    @staticmethod
    def resolve_zone(*, city: str, state: str = "") -> DeliveryZone:
        city_key = _normalize(city)
        state_key = _normalize(state) if state else ""

        zones = DeliveryZone.objects.filter(is_active=True).order_by("sort_order", "id")
        for zone in zones:
            if city_key in {_normalize(item) for item in zone.cities}:
                return zone
            if state_key and state_key in {_normalize(item) for item in zone.states}:
                return zone

        raise UndeliverableAddressError(
            f"Delivery is not available for {city}. Please choose a supported city."
        )

    @staticmethod
    def calculate_fee(
        zone: DeliveryZone,
        subtotal: Decimal,
        delivery_type: str = Order.DeliveryType.COURIER,
    ) -> Decimal:
        if delivery_type == Order.DeliveryType.PICKUP:
            return Decimal("0.00")

        if zone.free_delivery_threshold and subtotal >= zone.free_delivery_threshold:
            if delivery_type == Order.DeliveryType.EXPRESS:
                return zone.express_fee
            return Decimal("0.00")

        if delivery_type == Order.DeliveryType.EXPRESS:
            return zone.express_fee or zone.delivery_fee
        return zone.delivery_fee

    @staticmethod
    def validate_minimum_order(zone: DeliveryZone, subtotal: Decimal) -> None:
        if subtotal < zone.min_order_amount:
            raise MinimumOrderError(
                f"Minimum order for {zone.name} is {int(zone.min_order_amount)} تومان."
            )

    @staticmethod
    def default_delivery_type(payment_method: str) -> str:
        """Legacy helper — new checkout always uses pickup."""
        if payment_method == Order.PaymentMethod.COD:
            return Order.DeliveryType.COD
        return Order.DeliveryType.COURIER

    @staticmethod
    def default_fulfillment_type() -> str:
        return Order.DeliveryType.PICKUP


@dataclass
class CheckoutResult:
    order: Order
    payment: object | None
    payment_method: str
    checkout_url: str | None = None


class DeliveryServiceCheckout:
    """Checkout orchestration — online payment + in-store pickup only."""

    @staticmethod
    def _resolve_in_progress_checkout(cart, payment_method: str) -> CheckoutResult | None:
        if not cart.active_checkout_order_id:
            return None

        order = cart.active_checkout_order
        if not cart_services.is_order_checkout_in_progress(order):
            cart_services.clear_active_checkout_order(cart)
            return None

        payment = order.payments.order_by("-created_at").first()
        if payment is None and payment_method == Order.PaymentMethod.ONLINE:
            raise CheckoutAlreadyInProgress(
                "Checkout is already in progress for this cart."
            )

        checkout_url = getattr(payment, "checkout_url", None) if payment else None
        return CheckoutResult(
            order=order,
            payment=payment,
            payment_method=payment_method,
            checkout_url=checkout_url or None,
        )

    @staticmethod
    def _cleanup_failed_checkout(cart, order: Order | None) -> None:
        if order is not None and order.pk:
            OrderService.release_stock(order)
            order.delete()
        cart_services.clear_active_checkout_order(cart)

    @staticmethod
    @transaction.atomic
    def process_checkout(cart, customer: dict, *, user=None) -> CheckoutResult:
        configured_method = settings.DEFAULT_PAYMENT_METHOD
        if configured_method == Order.PaymentMethod.COD:
            logger.info(
                "DEFAULT_PAYMENT_METHOD=cod is deprecated; checkout uses online payment only."
            )

        payment_method = Order.PaymentMethod.ONLINE

        cart, cart_items = cart_services.lock_cart_for_checkout(cart)

        existing = DeliveryServiceCheckout._resolve_in_progress_checkout(cart, payment_method)
        if existing is not None:
            return existing

        if not cart_items:
            raise CheckoutError(str(EmptyCartError("Cannot checkout an empty cart.")))

        if not customer.get("phone"):
            raise CheckoutError("شماره تماس برای ثبت سفارش الزامی است.")

        subtotal = cart_services.calculate_subtotal(cart_items)
        delivery_type = DeliveryService.default_fulfillment_type()
        delivery_fee = Decimal("0.00")

        from growth.checkout_integration import GrowthCheckoutFacade

        growth_ctx = GrowthCheckoutFacade.prepare(cart, user, customer, subtotal)
        if growth_ctx.error:
            raise CheckoutError(growth_ctx.error)

        checkout_data = {
            **customer,
            "payment_method": payment_method,
            "delivery_type": delivery_type,
            "delivery_zone_id": None,
            "delivery_fee": delivery_fee,
        }

        order = None
        try:
            order = create_order_from_cart(cart, checkout_data, user=user, cart_items=cart_items)
            cart_services.set_active_checkout_order(cart, order)
            GrowthCheckoutFacade.apply_to_order(order, growth_ctx, user=user)
            finalize_checkout_stock(cart, order)
        except Exception as exc:
            DeliveryServiceCheckout._cleanup_failed_checkout(cart, order)
            raise CheckoutError(str(exc)) from exc

        try:
            payment = PaymentService.initiate_online(order)
        except PaymentError as exc:
            logger.error(
                "Online payment error during checkout",
                extra={
                    "order_id": order.pk,
                    "order_number": order.order_number,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
                exc_info=True,
            )
            DeliveryServiceCheckout._cleanup_failed_checkout(cart, order)
            raise CheckoutError(ONLINE_PAYMENT_UNAVAILABLE_MESSAGE) from exc

        order.payment_status = Order.PaymentStatus.PENDING_PAYMENT
        order.status = Order.Status.PENDING_PAYMENT
        order.save(update_fields=["payment_status", "status", "updated_at"])
        return CheckoutResult(
            order=order,
            payment=payment,
            payment_method=payment_method,
            checkout_url=payment.checkout_url,
        )


process_checkout = DeliveryServiceCheckout.process_checkout
