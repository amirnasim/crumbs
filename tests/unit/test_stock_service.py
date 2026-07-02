"""Unit tests for StockService / inventory reservations."""

import pytest
from django.utils import timezone

from inventory.exceptions import InsufficientStockError
from inventory.models import ProductInventory, StockReservation
from orders.models import Order
from products.services.stock_service import StockService
from tests.factories import create_order, create_product, create_user


@pytest.mark.django_db
class TestStockService:
    def test_reserve_for_order_reduces_available_quantity(self):
        user = create_user()
        product = create_product(stock_quantity=10)
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        StockService.reserve_for_order(order)
        inventory = ProductInventory.objects.get(product=product)
        assert inventory.reserved_quantity == 1
        assert inventory.available_quantity == 9

    def test_oversell_raises_when_stock_insufficient(self):
        user = create_user()
        product = create_product(stock_quantity=1)
        from inventory.models import ProductInventory

        ProductInventory.objects.filter(product=product).update(allow_preorder=False)
        order1 = create_order(user, product, status=Order.Status.PENDING_PAYMENT, payment_status=Order.PaymentStatus.PENDING_PAYMENT)
        order2 = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        order2.order_number = "CR-TEST-9999"
        order2.save(update_fields=["order_number"])
        StockService.reserve_for_order(order1)
        with pytest.raises(InsufficientStockError):
            StockService.reserve_for_order(order2)

    def test_release_reservations_restores_stock(self):
        user = create_user()
        product = create_product(stock_quantity=5)
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        StockService.reserve_for_order(order)
        StockService.release_reservations(order)
        inventory = ProductInventory.objects.get(product=product)
        assert inventory.reserved_quantity == 0
        assert inventory.available_quantity == 5

    def test_fulfill_reduces_stock_quantity(self):
        user = create_user()
        product = create_product(stock_quantity=5)
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.COD_CONFIRMED,
            payment_method=Order.PaymentMethod.COD,
        )
        StockService.reserve_for_order(order)
        StockService.confirm_reservations(order)
        StockService.fulfill_reservations(order)
        inventory = ProductInventory.objects.get(product=product)
        assert inventory.stock_quantity == 4
        assert inventory.reserved_quantity == 0

    def test_expire_stale_reservations(self):
        user = create_user()
        product = create_product(stock_quantity=5)
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        )
        StockService.reserve_for_order(order)
        StockReservation.objects.filter(order=order).update(
            expires_at=timezone.now() - timezone.timedelta(minutes=5)
        )
        expired = StockService.expire_stale_reservations()
        assert expired == 1
        inventory = ProductInventory.objects.get(product=product)
        assert inventory.reserved_quantity == 0
