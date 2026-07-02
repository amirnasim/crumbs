"""Unit tests for OrderService state transitions."""

import pytest

from delivery.exceptions import InvalidTransitionError
from delivery.state_machine import validate_transition
from orders.models import Order
from orders.services.order_service import OrderService
from tests.factories import create_order, create_product, create_user


@pytest.mark.django_db
class TestOrderServiceTransitions:
    def test_valid_transition_pending_to_confirmed(self):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        OrderService.transition(order, Order.Status.CONFIRMED_BY_SHOP)
        order.refresh_from_db()
        assert order.status == Order.Status.CONFIRMED_BY_SHOP

    def test_invalid_transition_raises(self):
        user = create_user()
        product = create_product()
        order = create_order(user, product, status=Order.Status.DELIVERED, payment_status=Order.PaymentStatus.CASH_RECEIVED)
        with pytest.raises(InvalidTransitionError):
            validate_transition(order, Order.Status.PREPARING)

    def test_cancel_releases_stock_and_sets_cancelled(self, mocker):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.COD_PENDING,
        )
        release = mocker.patch("orders.services.order_service.StockService.release_reservations")
        OrderService.cancel(order, reason="test")
        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED
        release.assert_called_once()

    def test_finalize_online_payment_is_idempotent(self, mocker):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        confirm = mocker.patch("orders.services.order_service.StockService.confirm_reservations")
        OrderService.finalize_online_payment(order)
        OrderService.finalize_online_payment(order)
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert confirm.call_count == 1

    def test_finalize_online_payment_transitions_to_confirmed(self, mocker):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        mocker.patch("orders.services.order_service.StockService.confirm_reservations")
        OrderService.finalize_online_payment(order)
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP

    def test_cod_confirm_requires_cod_pending(self):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
        )
        from orders.exceptions import CheckoutError

        with pytest.raises(CheckoutError):
            OrderService.confirm_cod(order)

    def test_sms_event_mapping_for_preparing(self):
        event = OrderService.sms_event_for_status(Order.Status.PREPARING)
        assert event == "order_preparing"
