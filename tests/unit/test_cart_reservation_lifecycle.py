"""Cart and order stock reservation lifecycle."""

import pytest
from django.test import override_settings

from cart.services import add_item, clear_cart, remove_item
from delivery.services import process_checkout
from inventory.exceptions import InsufficientStockError
from inventory.models import ProductInventory, StockReservation
from orders.exceptions import CheckoutError
from orders.models import Order
from products.services.stock_service import StockService
from tests.factories import CUSTOMER, create_cart_with_item, create_product, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


@pytest.mark.django_db
class TestCartReservationCleanup:
    def test_remove_item_releases_cart_reservation(self, user, product):
        cart = create_cart_with_item(user, product, quantity=2)
        inventory = ProductInventory.objects.get(product=product)

        assert inventory.reserved_quantity == 2
        assert StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).count() == 1

        remove_item(cart, product)

        inventory.refresh_from_db()
        assert inventory.reserved_quantity == 0
        assert not StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).exists()
        assert cart.items.count() == 0

    def test_clear_cart_releases_cart_reservations(self, user, product):
        cart = create_cart_with_item(user, product, quantity=1)
        product2 = create_product(name="Second Cookie", price=product.price)
        add_item(cart, product2, 2)

        inventory1 = ProductInventory.objects.get(product=product)
        inventory2 = ProductInventory.objects.get(product=product2)
        assert inventory1.reserved_quantity == 1
        assert inventory2.reserved_quantity == 2
        assert StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).count() == 2

        clear_cart(cart)

        inventory1.refresh_from_db()
        inventory2.refresh_from_db()
        assert inventory1.reserved_quantity == 0
        assert inventory2.reserved_quantity == 0
        assert not StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).exists()
        assert cart.items.count() == 0

    def test_release_cart_reservations_is_idempotent(self, user, product):
        cart = create_cart_with_item(user, product, quantity=1)
        inventory = ProductInventory.objects.get(product=product)

        StockService.release_cart_reservations(cart)
        inventory.refresh_from_db()
        assert inventory.reserved_quantity == 0

        released = StockService.release_cart_reservations(cart)
        assert released == 0


@pytest.mark.django_db
class TestCheckoutReservationLifecycle:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_checkout_does_not_double_reserve_stock(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product, quantity=2)
        inventory = ProductInventory.objects.get(product=product)
        assert inventory.reserved_quantity == 2

        result = process_checkout(cart, CUSTOMER, user=user)

        inventory.refresh_from_db()
        assert inventory.reserved_quantity == 2
        assert not StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).exists()
        order_reservations = StockReservation.objects.filter(
            order=result.order,
            status=StockReservation.Status.ACTIVE,
        )
        assert order_reservations.count() == 1
        assert order_reservations.get().quantity == 2

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_successful_checkout_has_only_order_reservation(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product, quantity=1)
        result = process_checkout(cart, CUSTOMER, user=user)

        assert StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).count() == 0
        assert StockReservation.objects.filter(
            order=result.order,
            status=StockReservation.Status.ACTIVE,
        ).count() == 1

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_failed_checkout_keeps_cart_intact(self, user, product, mocker, mock_stripe_checkout):
        mocker.patch.object(
            StockService,
            "reserve_for_order",
            side_effect=InsufficientStockError("not enough stock"),
        )
        cart = create_cart_with_item(user, product, quantity=1)

        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)

        cart.refresh_from_db()
        assert cart.items.count() == 1
        assert StockReservation.objects.filter(
            cart=cart,
            status=StockReservation.Status.ACTIVE,
        ).count() == 1

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_failed_checkout_does_not_leave_orphan_order(self, user, product, mocker, mock_stripe_checkout):
        mocker.patch.object(
            StockService,
            "reserve_for_order",
            side_effect=InsufficientStockError("not enough stock"),
        )
        cart = create_cart_with_item(user, product, quantity=1)

        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)

        assert Order.objects.filter(user=user).count() == 0

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_failed_checkout_does_not_leave_stale_order_reservation(
        self, user, product, mocker, mock_stripe_checkout
    ):
        mocker.patch.object(
            StockService,
            "reserve_for_order",
            side_effect=InsufficientStockError("not enough stock"),
        )
        cart = create_cart_with_item(user, product, quantity=1)

        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)

        assert not StockReservation.objects.filter(
            order__isnull=False,
            status=StockReservation.Status.ACTIVE,
        ).exists()
