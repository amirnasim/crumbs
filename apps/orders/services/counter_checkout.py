"""In-store counter checkout — cash or card payment at the register."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from cart import services as cart_services
from orders.exceptions import CheckoutError, EmptyCartError
from orders.models import Order
from orders.services import create_order_from_cart, finalize_checkout_stock
from payments.models import Payment
from payments.services import PaymentService

COUNTER_PAYMENT_METHODS = {
    Order.PaymentMethod.CASH,
    Order.PaymentMethod.COUNTER_CARD,
}


@dataclass
class CounterCheckoutResult:
    order: Order
    payment: Payment
    payment_method: str


class CounterCheckoutService:
    @staticmethod
    @transaction.atomic
    def process_checkout(
        cart,
        customer: dict,
        *,
        payment_method: str,
        user=None,
    ) -> CounterCheckoutResult:
        if payment_method not in COUNTER_PAYMENT_METHODS:
            raise CheckoutError(f"Unsupported counter payment method: {payment_method}")

        if not customer.get("phone"):
            raise CheckoutError("شماره تماس برای ثبت سفارش الزامی است.")

        cart, cart_items = cart_services.lock_cart_for_checkout(cart)
        if not cart_items:
            raise CheckoutError(str(EmptyCartError("Cannot checkout an empty cart.")))

        subtotal = cart_services.calculate_subtotal(cart_items)
        checkout_data = {
            **customer,
            "payment_method": payment_method,
            "delivery_type": Order.DeliveryType.PICKUP,
            "delivery_zone_id": None,
            "delivery_fee": Decimal("0.00"),
        }

        order = create_order_from_cart(
            cart,
            checkout_data,
            user=user,
            cart_items=cart_items,
            initial_status=Order.Status.AWAITING_PAYMENT,
            initial_payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        finalize_checkout_stock(cart, order)
        payment = PaymentService.initiate_counter_payment(order, payment_method)
        return CounterCheckoutResult(
            order=order,
            payment=payment,
            payment_method=payment_method,
        )


process_counter_checkout = CounterCheckoutService.process_checkout
