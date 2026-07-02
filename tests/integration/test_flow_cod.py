"""Legacy COD order lifecycle — admin actions on historical orders only."""

from decimal import Decimal

import pytest
from django.test import override_settings

from delivery.services import process_checkout
from inventory.models import ProductInventory, StockReservation
from orders.models import Order
from orders.services.order_service import OrderService
from payments.models import Payment
from payments.services import PaymentService
from tests.factories import CUSTOMER, create_cart_with_item, create_order
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


@pytest.mark.integration
@pytest.mark.django_db
class TestLegacyCODOrderFlow:
    def test_legacy_cod_order_full_lifecycle(self, user, product, delivery_zone):
        inventory = ProductInventory.objects.get(product=product)
        initial_stock = inventory.stock_quantity

        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.COD,
            delivery_type=Order.DeliveryType.COD,
            delivery_fee=Decimal("50000"),
            payment_status=Order.PaymentStatus.COD_PENDING,
            status=Order.Status.CONFIRMED_BY_SHOP,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.COD,
            status=Payment.Status.PENDING,
            amount=order.total,
            metadata={"method": "cash_on_delivery"},
        )
        OrderService.reserve_stock(order)
        OrderService.confirm_stock(order)
        inventory.refresh_from_db()
        assert inventory.reserved_quantity >= 1
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.CONFIRMED,
        ).exists()

        OrderService.confirm_cod(order)
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.COD_CONFIRMED

        for status in (
            Order.Status.PREPARING,
            Order.Status.PACKAGED,
            Order.Status.OUT_FOR_DELIVERY,
        ):
            OrderService.transition(order, status)
            order.refresh_from_db()

        PaymentService.mark_cod_cash_received(order, payment)
        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert order.status == Order.Status.DELIVERED
        assert order.payment_status == Order.PaymentStatus.CASH_RECEIVED
        assert payment.status == Payment.Status.SUCCEEDED
        assert inventory.stock_quantity == initial_stock - 1
        assert not StockReservation.objects.filter(
            order=order,
            status__in=[
                StockReservation.Status.ACTIVE,
                StockReservation.Status.CONFIRMED,
            ],
        ).exists()

        PaymentService.mark_cod_cash_received(order, payment)
        inventory.refresh_from_db()
        assert inventory.stock_quantity == initial_stock - 1

    @override_settings(**{**STRIPE_ONLINE_SETTINGS, "DEFAULT_PAYMENT_METHOD": "cod"})
    def test_checkout_always_uses_online_payment(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)

        order = result.order
        assert order.payment_method == Order.PaymentMethod.ONLINE
        assert order.delivery_type == Order.DeliveryType.PICKUP
        assert order.delivery_fee == Decimal("0.00")
        assert order.delivery_zone_id is None
        assert result.checkout_url is not None
        assert result.payment.provider != Payment.Provider.COD
