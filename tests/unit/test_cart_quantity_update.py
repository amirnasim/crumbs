"""Regression tests for cart quantity updates above 10 and error handling."""

import logging

import pytest
from django.contrib.messages import get_messages
from django.test import Client
from django.urls import reverse

from cart.exceptions import INVALID_QUANTITY_MESSAGE, STOCK_CAPACITY_EXCEEDED_MESSAGE
from cart.services import calculate_subtotal
from inventory.models import DailyProductionCapacity, ProductInventory, StockReservation
from tests.factories import create_cart_with_item, create_product, create_user


@pytest.fixture
def client():
    return Client()


def _post_cart_update(client, item, quantity):
    return client.post(
        reverse("core:cart"),
        {"action": "update", f"quantity_{item.pk}": str(quantity)},
    )


@pytest.mark.django_db
class TestCartQuantityEleven:
    def test_increase_10_to_11_succeeds_with_sufficient_stock(self, client, user, product):
        cart = create_cart_with_item(user, product, quantity=10)
        item = cart.items.get()
        inventory = ProductInventory.objects.get(product=product)
        client.force_login(user)

        response = _post_cart_update(client, item, 11)

        assert response.status_code == 302
        item.refresh_from_db()
        inventory.refresh_from_db()
        reservation = StockReservation.objects.get(
            cart=cart,
            product=product,
            status=StockReservation.Status.ACTIVE,
        )
        assert item.quantity == 11
        assert reservation.quantity == 11
        assert inventory.reserved_quantity == 11

    def test_decrease_11_to_10_succeeds(self, client, user, product):
        cart = create_cart_with_item(user, product, quantity=11)
        item = cart.items.get()
        inventory = ProductInventory.objects.get(product=product)
        client.force_login(user)

        response = _post_cart_update(client, item, 10)

        assert response.status_code == 302
        item.refresh_from_db()
        inventory.refresh_from_db()
        reservation = StockReservation.objects.get(
            cart=cart,
            product=product,
            status=StockReservation.Status.ACTIVE,
        )
        assert item.quantity == 10
        assert reservation.quantity == 10
        assert inventory.reserved_quantity == 10

    def test_request_above_stock_shows_persian_error_not_500(self, client, user):
        product = create_product(stock_quantity=10, name="Ten Only")
        cart = create_cart_with_item(user, product, quantity=10)
        item = cart.items.get()
        client.force_login(user)

        response = _post_cart_update(client, item, 11)

        assert response.status_code == 302
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert STOCK_CAPACITY_EXCEEDED_MESSAGE in messages
        assert "سبد خرید بروزرسانی شد." not in messages

    def test_rejected_update_keeps_quantity_reservation_and_totals(self, client, user):
        product = create_product(stock_quantity=10, name="Frozen Ten", price=100_000)
        cart = create_cart_with_item(user, product, quantity=10)
        item = cart.items.get()
        inventory = ProductInventory.objects.get(product=product)
        reservation = StockReservation.objects.get(
            cart=cart,
            product=product,
            status=StockReservation.Status.ACTIVE,
        )
        previous_subtotal = calculate_subtotal(list(cart.items.all()))
        client.force_login(user)

        response = _post_cart_update(client, item, 11)

        assert response.status_code == 302
        item.refresh_from_db()
        inventory.refresh_from_db()
        reservation.refresh_from_db()
        assert item.quantity == 10
        assert reservation.quantity == 10
        assert inventory.reserved_quantity == 10
        assert calculate_subtotal(list(cart.items.all())) == previous_subtotal

    def test_daily_capacity_exceeded_shows_persian_error_not_500(self, client, user):
        product = create_product(stock_quantity=20, name="Capacity Limited")
        cart = create_cart_with_item(user, product, quantity=10)
        item = cart.items.get()
        DailyProductionCapacity.objects.filter(product=product).update(max_units=10)
        client.force_login(user)

        response = _post_cart_update(client, item, 11)

        assert response.status_code == 302
        item.refresh_from_db()
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert STOCK_CAPACITY_EXCEEDED_MESSAGE in messages
        assert item.quantity == 10


@pytest.mark.django_db
class TestCartInvalidQuantities:
    @pytest.mark.parametrize(
        "posted_quantity",
        ["", "abc", "1.5"],
    )
    def test_invalid_quantities_never_return_500(self, client, user, product, posted_quantity):
        cart = create_cart_with_item(user, product, quantity=2)
        item = cart.items.get()
        client.force_login(user)

        response = client.post(
            reverse("core:cart"),
            {"action": "update", f"quantity_{item.pk}": posted_quantity},
        )

        assert response.status_code == 302
        item.refresh_from_db()
        assert item.quantity == 2
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert any(INVALID_QUANTITY_MESSAGE in message or "Quantity must be" in message for message in messages)

    def test_zero_quantity_removes_item_without_error(self, client, user, product):
        cart = create_cart_with_item(user, product, quantity=2)
        item = cart.items.get()
        client.force_login(user)

        response = _post_cart_update(client, item, 0)

        assert response.status_code == 302
        assert cart.items.count() == 0


@pytest.mark.django_db
class TestCartUnexpectedFailureLogging:
    def test_unexpected_cart_exception_logs_safe_context_only(self, client, user, product, mocker, caplog):
        cart = create_cart_with_item(user, product, quantity=3)
        item = cart.items.get()
        client.force_login(user)
        mocker.patch(
            "core.views.set_item_quantity",
            side_effect=RuntimeError("database exploded"),
        )

        with caplog.at_level(logging.ERROR, logger="core.views"):
            with pytest.raises(RuntimeError, match="database exploded"):
                _post_cart_update(client, item, 4)

        record = next(r for r in caplog.records if r.levelname == "ERROR")
        assert "Unexpected cart quantity update failure" in record.message
        assert record.cart_id == cart.pk
        assert record.product_id == product.pk
        assert record.previous_quantity == 3
        assert record.requested_quantity == "4"
        assert "database exploded" not in getattr(record, "phone", "")
        log_text = record.getMessage()
        for forbidden in ("phone", "email", "address", "cookie"):
            assert forbidden not in log_text.lower()
