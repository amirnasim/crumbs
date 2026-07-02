"""Concurrency tests — stock reservation under parallel checkout."""

import concurrent.futures

import pytest
from django.db import connection, transaction
from django.db.utils import OperationalError
from django.test import override_settings

from delivery.services import process_checkout
from inventory.exceptions import InsufficientStockError
from inventory.models import ProductInventory
from orders.exceptions import CheckoutError
from orders.models import Order
from tests.factories import CUSTOMER, create_cart_with_item, create_product, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


def _requires_postgres():
    if connection.vendor != "postgresql":
        pytest.skip("Concurrency tests require PostgreSQL (select_for_update semantics).")


def _close_db_connection():
    connection.close()


@pytest.mark.concurrency
@pytest.mark.django_db(transaction=True)
class TestStockRaceConditions:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_parallel_checkouts_do_not_oversell(self, mock_stripe_checkout):
        _requires_postgres()

        product = create_product(stock_quantity=5, name="Race Cookie")
        max_success = 5
        results = {"success": 0, "failed": 0}

        def attempt_checkout(user_index: int):
            try:
                user = create_user(username=f"race-{user_index}", email=f"race{user_index}@test.com")
                from products.models import Product

                prod = Product.objects.get(pk=product.pk)
                cart = create_cart_with_item(user, prod)
                customer = {**CUSTOMER, "email": user.email}
                try:
                    with transaction.atomic():
                        process_checkout(cart, customer, user=user)
                    return "success"
                except (InsufficientStockError, CheckoutError):
                    return "failed"
            except OperationalError:
                return "failed"
            finally:
                _close_db_connection()

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as pool:
            outcomes = list(pool.map(attempt_checkout, range(10)))

        results["success"] = outcomes.count("success")
        results["failed"] = outcomes.count("failed")

        inventory = ProductInventory.objects.get(product=product)
        assert results["success"] <= max_success
        assert inventory.reserved_quantity <= inventory.stock_quantity
        assert inventory.available_quantity >= 0

    @pytest.mark.slow
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_fifty_parallel_reservations(self, mock_stripe_checkout):
        _requires_postgres()

        product = create_product(stock_quantity=10, name="Hot Cookie")

        def reserve_once(index: int):
            try:
                user = create_user(username=f"hot-{index}", email=f"hot{index}@test.com")
                from products.models import Product

                prod = Product.objects.get(pk=product.pk)
                cart = create_cart_with_item(user, prod)
                customer = {**CUSTOMER, "email": user.email}
                try:
                    with transaction.atomic():
                        process_checkout(cart, customer, user=user)
                    return True
                except (InsufficientStockError, CheckoutError):
                    return False
            except OperationalError:
                return False
            finally:
                _close_db_connection()

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as pool:
            successes = sum(1 for ok in pool.map(reserve_once, range(50)) if ok)

        inventory = ProductInventory.objects.get(product=product)
        assert successes <= 10
        assert inventory.reserved_quantity <= 10

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_concurrent_checkout_same_cart_creates_single_order(self, mock_stripe_checkout):
        _requires_postgres()

        user = create_user(username="same-cart", email="samecart@test.com")
        product = create_product(stock_quantity=20, name="Shared Cart Cookie")
        cart = create_cart_with_item(user, product)
        cart_id = cart.pk
        customer = {**CUSTOMER, "email": user.email}

        def attempt_checkout():
            try:
                from cart.models import Cart

                locked_cart = Cart.objects.get(pk=cart_id)
                try:
                    with transaction.atomic():
                        return process_checkout(locked_cart, customer, user=user)
                except CheckoutError:
                    return None
            finally:
                _close_db_connection()

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            outcomes = list(pool.map(lambda _: attempt_checkout(), range(2)))

        successful = [outcome for outcome in outcomes if outcome is not None]
        assert len(successful) == 1
        assert Order.objects.filter(user=user).count() == 1
