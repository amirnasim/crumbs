"""Counter payment workflow — cash and card at the register."""

import pytest

from inventory.models import ProductInventory, StockReservation
from orders.models import Order
from orders.services.counter_checkout import process_counter_checkout
from orders.services.order_service import OrderService
from payments.exceptions import PaymentError
from payments.models import Payment
from payments.services import PaymentService
from tests.factories import CUSTOMER, create_cart_with_item, create_product, create_user


@pytest.mark.django_db
class TestCounterPaymentFlow:
    def _checkout(self, user, product, payment_method):
        cart = create_cart_with_item(user, product)
        return process_counter_checkout(cart, CUSTOMER, payment_method=payment_method, user=user)

    def test_cash_checkout_creates_awaiting_payment_order(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order
        payment = result.payment

        assert order.status == Order.Status.AWAITING_PAYMENT
        assert order.payment_method == Order.PaymentMethod.CASH
        assert order.delivery_type == Order.DeliveryType.PICKUP
        assert payment.provider == Payment.Provider.CASH
        assert payment.status == Payment.Status.PENDING
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.ACTIVE,
        ).exists()

    def test_card_checkout_creates_awaiting_payment_order(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.COUNTER_CARD)
        order = result.order
        payment = result.payment

        assert order.status == Order.Status.AWAITING_PAYMENT
        assert order.payment_method == Order.PaymentMethod.COUNTER_CARD
        assert payment.provider == Payment.Provider.COUNTER_CARD
        assert payment.status == Payment.Status.PENDING

    def test_mark_cash_received_moves_order_to_preparing(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order
        payment = result.payment
        inventory = ProductInventory.objects.get(product=product)
        initial_stock = inventory.stock_quantity

        PaymentService.mark_counter_cash_received(order, payment, actor="staff")
        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.PREPARING
        assert inventory.stock_quantity == initial_stock
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.CONFIRMED,
        ).exists()

    def test_mark_card_received_moves_order_to_preparing(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.COUNTER_CARD)
        order = result.order
        payment = result.payment

        PaymentService.mark_counter_card_received(order, payment, actor="staff")
        order.refresh_from_db()
        payment.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.PREPARING

    def test_duplicate_counter_payment_is_idempotent(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order
        payment = result.payment
        inventory = ProductInventory.objects.get(product=product)

        PaymentService.mark_counter_cash_received(order, payment, actor="staff")
        inventory.refresh_from_db()
        reserved_after_first = inventory.reserved_quantity

        PaymentService.mark_counter_cash_received(order, payment, actor="staff")
        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert order.status == Order.Status.PREPARING
        assert inventory.reserved_quantity == reserved_after_first
        assert Payment.objects.filter(order=order, provider=Payment.Provider.CASH).count() == 1

    def test_wrong_counter_action_is_rejected(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order
        payment = result.payment

        with pytest.raises(PaymentError, match="provider does not match"):
            PaymentService.mark_counter_card_received(order, payment, actor="staff")

    def test_finalize_counter_payment_requires_awaiting_status(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order
        payment = result.payment

        PaymentService.mark_counter_cash_received(order, payment, actor="staff")
        order.refresh_from_db()

        finalized = OrderService.finalize_counter_payment(order, actor="staff")
        assert finalized.status == Order.Status.PREPARING

    def test_counter_checkout_does_not_create_duplicate_payment(self, user, product):
        result = self._checkout(user, product, Order.PaymentMethod.CASH)
        order = result.order

        second = PaymentService.initiate_counter_payment(order, Order.PaymentMethod.CASH)
        assert second.pk == result.payment.pk
