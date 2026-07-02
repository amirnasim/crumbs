"""Table QR / in-cafe session — ?table= query param handling."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from core.table_session import (
    MAX_TABLE_LENGTH,
    SESSION_CAFE_TABLE,
    capture_table_from_query,
    get_table_from_session,
    sanitize_table_number,
)
from orders.models import Order
from tests.factories import create_cart_with_item, create_order, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS

User = get_user_model()


@pytest.fixture
def client():
    return Client()


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("01", "01"),
        ("  12  ", "12"),
        ("میز ۵", "میز ۵"),
        ("a" * 25, "a" * MAX_TABLE_LENGTH),
        ("", ""),
        (None, ""),
        ("  \n\t  ", ""),
    ],
)
def test_sanitize_table_number(raw, expected):
    assert sanitize_table_number(raw) == expected


@pytest.mark.django_db
class TestTableSessionCapture:
    def test_shop_table_param_stored_in_session(self, client):
        response = client.get("/shop/?table=01")

        assert response.status_code == 200
        assert client.session[SESSION_CAFE_TABLE] == "01"
        assert get_table_from_session(response.wsgi_request) == "01"

    def test_cart_table_param_stored_in_session(self, client):
        response = client.get("/cart/?table=07")

        assert response.status_code == 200
        assert client.session[SESSION_CAFE_TABLE] == "07"

    def test_checkout_table_param_stored_in_session(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get("/checkout/?table=03")

        assert response.status_code == 200
        assert client.session[SESSION_CAFE_TABLE] == "03"

    def test_table_persists_across_requests_without_query_param(self, client):
        client.get("/shop/?table=01")
        response = client.get("/cart/")

        assert response.status_code == 200
        assert client.session[SESSION_CAFE_TABLE] == "01"
        assert b"01" in response.content

    def test_invalid_long_table_is_truncated(self, client):
        long_table = "x" * 25
        client.get(f"/shop/?table={long_table}")

        assert client.session[SESSION_CAFE_TABLE] == "x" * MAX_TABLE_LENGTH

    def test_empty_table_param_clears_session(self, client):
        client.get("/shop/?table=01")
        client.get("/shop/?table=")

        assert SESSION_CAFE_TABLE not in client.session


@pytest.mark.django_db
class TestTableCheckoutPrefill:
    def test_checkout_prefills_pickup_note_from_session(self, client, user, product):
        create_cart_with_item(user, product)
        client.get("/shop/?table=01")
        client.force_login(user)

        response = client.get(reverse("core:checkout"))

        assert response.status_code == 200
        assert 'value="01"' in response.content.decode()

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_order_stores_table_number_from_checkout(self, client, user, product, mock_stripe_checkout):
        create_cart_with_item(user, product)
        client.get("/shop/?table=09")
        client.force_login(user)

        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": "Sara",
                "phone": "09121234567",
                "email": "",
                "pickup_note": "09",
                "payment_method": Order.PaymentMethod.CASH,
            },
        )

        assert response.status_code == 302
        order = Order.objects.get(user=user)
        assert order.notes == "09"

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_user_can_remove_table_from_checkout(self, client, user, product, mock_stripe_checkout):
        create_cart_with_item(user, product)
        client.get("/shop/?table=01")
        client.force_login(user)

        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": "Sara",
                "phone": "09121234567",
                "email": "",
                "pickup_note": "",
                "payment_method": Order.PaymentMethod.CASH,
            },
        )

        assert response.status_code == 302
        order = Order.objects.get(user=user)
        assert order.notes == ""
        assert SESSION_CAFE_TABLE not in client.session


@pytest.mark.django_db
class TestTableKitchenDisplay:
    def test_kitchen_queue_displays_table_note(self, client, product):
        staff = User.objects.create_user(
            username="table-staff",
            email="table-staff@example.com",
            password="pass12345",
            is_staff=True,
        )
        user = create_user(username="table-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )
        order.notes = "01"
        order.save(update_fields=["notes", "updated_at"])

        client.force_login(staff)
        response = client.get("/admin/kitchen/")

        assert response.status_code == 200
        assert b"01" in response.content


@pytest.mark.django_db
def test_capture_table_from_query_without_param_returns_existing(client):
    request = client.get("/shop/").wsgi_request
    request.session[SESSION_CAFE_TABLE] = "05"

    assert capture_table_from_query(request) == "05"
