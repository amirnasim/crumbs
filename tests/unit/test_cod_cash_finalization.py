"""Unit tests for COD cash received finalization."""

import pytest
from django.utils import timezone

from inventory.models import DailyProductionCapacity, ProductInventory, StockReservation
from orders.models import Order
from orders.services.order_service import OrderService
from payments.models import Payment
from payments.services import PaymentService
from tests.factories import create_order, create_product, create_user


@pytest.mark.django_db
class TestCODCashFinalization:
    def _create_cod_order_with_payment(self, *, payment_status=Order.PaymentStatus.COD_CONFIRMED):
        user = create_user()
        product = create_product(stock_quantity=20)
        order = create_order(
            user,
            product,
            status=Order.Status.OUT_FOR_DELIVERY,
            payment_status=payment_status,
            payment_method=Order.PaymentMethod.COD,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.COD,
            status=Payment.Status.PENDING,
            amount=order.total,
            currency="irr",
        )
        production_date = timezone.localdate()
        DailyProductionCapacity.objects.create(
            product=product,
            production_date=production_date,
            max_units=50,
        )
        StockReservation.objects.create(
            product=product,
            order=order,
            quantity=1,
            production_date=production_date,
            status=StockReservation.Status.CONFIRMED,
        )
        inventory = ProductInventory.objects.get(product=product)
        inventory.reserved_quantity = 1
        inventory.save(update_fields=["reserved_quantity", "updated_at"])
        return order, payment, product, inventory

    def test_mark_cod_cash_received_marks_payment_and_consumes_inventory(self):
        order, payment, product, inventory = self._create_cod_order_with_payment()
        initial_stock = inventory.stock_quantity

        PaymentService.mark_cod_cash_received(order, payment, actor="admin")

        payment.refresh_from_db()
        order.refresh_from_db()
        inventory.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert payment.metadata.get("cash_received_event") == "cod_cash_finalized"
        assert order.payment_status == Order.PaymentStatus.CASH_RECEIVED
        assert order.status == Order.Status.DELIVERED
        assert inventory.reserved_quantity == 0
        assert inventory.stock_quantity == initial_stock - 1
        assert not StockReservation.objects.filter(
            order=order,
            status__in=[
                StockReservation.Status.ACTIVE,
                StockReservation.Status.CONFIRMED,
            ],
        ).exists()

    def test_repeated_mark_cod_cash_received_is_idempotent(self):
        order, payment, product, inventory = self._create_cod_order_with_payment()

        PaymentService.mark_cod_cash_received(order, payment, actor="admin")
        inventory.refresh_from_db()
        stock_after_first = inventory.stock_quantity
        reserved_after_first = inventory.reserved_quantity

        PaymentService.mark_cod_cash_received(order, payment, actor="admin")
        inventory.refresh_from_db()
        payment.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert inventory.stock_quantity == stock_after_first
        assert inventory.reserved_quantity == reserved_after_first

    def test_ensure_cod_finalizes_pending_payment_when_already_cash_received(self):
        order, payment, product, inventory = self._create_cod_order_with_payment(
            payment_status=Order.PaymentStatus.CASH_RECEIVED,
        )
        order.status = Order.Status.DELIVERED
        order.save(update_fields=["status", "updated_at"])
        initial_stock = inventory.stock_quantity

        PaymentService.ensure_cod_cash_finalized(order, actor="admin")

        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert inventory.reserved_quantity == 0
        assert inventory.stock_quantity == initial_stock - 1

    def test_delivered_without_cash_received_does_not_finalize_payment(self):
        order, payment, product, inventory = self._create_cod_order_with_payment()
        order.status = Order.Status.DELIVERED
        order.payment_status = Order.PaymentStatus.COD_CONFIRMED
        order.save(update_fields=["status", "payment_status", "updated_at"])

        PaymentService.ensure_cod_cash_finalized(order, actor="admin")

        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert payment.status == Payment.Status.PENDING
        assert inventory.reserved_quantity == 1

    def test_complete_delivery_requires_cash_received_for_cod(self):
        order, payment, product, inventory = self._create_cod_order_with_payment()
        from orders.exceptions import CheckoutError

        with pytest.raises(CheckoutError):
            OrderService.complete_delivery(order, actor="admin")

        payment.refresh_from_db()
        assert payment.status == Payment.Status.PENDING
