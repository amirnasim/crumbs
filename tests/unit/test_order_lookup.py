"""Staff order quick lookup page."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.order_lookup import (
    DEFAULT_LOOKUP_LIMIT,
    recent_active_orders_queryset,
    search_orders_queryset,
)
from orders.models import Order
from tests.factories import create_order, create_user

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="lookup-staff",
        email="lookup-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


def _lookup_url(**params):
    url = reverse("admin:crumbs_order_lookup")
    if not params:
        return url
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{url}?{query}"


@pytest.mark.django_db
class TestOrderLookupAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/order-lookup/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/order-lookup/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_staff_user_can_view_lookup_page(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/order-lookup/")

        assert response.status_code == 200
        assert b"Order Lookup" in response.content


@pytest.mark.django_db
class TestOrderLookupSearch:
    def test_staff_can_search_by_order_number(self, client, staff_user, product):
        user = create_user(username="lookup-order-number")
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.get(_lookup_url(q=order.order_number))

        content = response.content.decode()
        assert response.status_code == 200
        assert order.order_number in content
        assert reverse("admin:orders_order_change", args=[order.pk]) in content

    def test_staff_can_search_by_phone(self, client, staff_user, product):
        user = create_user(username="lookup-phone")
        order = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
        )
        order.phone = "09129998877"
        order.save(update_fields=["phone", "updated_at"])

        client.force_login(staff_user)
        response = client.get(_lookup_url(q="09129998877"))

        assert response.status_code == 200
        assert order.order_number.encode() in response.content

    def test_staff_can_search_by_name(self, client, staff_user, product):
        user = create_user(username="lookup-name")
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
        )
        order.first_name = "Parisa"
        order.last_name = "Karimi"
        order.save(update_fields=["first_name", "last_name", "updated_at"])

        client.force_login(staff_user)
        response = client.get(_lookup_url(q="Parisa"))

        assert response.status_code == 200
        assert b"Parisa Karimi" in response.content

    def test_staff_can_search_by_table_note(self, client, staff_user, product):
        user = create_user(username="lookup-table")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
        )
        order.notes = "Table 12"
        order.save(update_fields=["notes", "updated_at"])

        client.force_login(staff_user)
        response = client.get(_lookup_url(q="Table 12"))

        content = response.content.decode()
        assert response.status_code == 200
        assert order.order_number in content
        assert reverse("admin:crumbs_pickup_screen") in content


@pytest.mark.django_db
class TestOrderLookupDefaults:
    def test_default_recent_active_orders_displayed(self, client, staff_user, product):
        user = create_user(username="lookup-default")
        active = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )
        delivered = create_order(
            user,
            product,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.get("/admin/order-lookup/")

        content = response.content.decode()
        assert response.status_code == 200
        assert active.order_number in content
        assert delivered.order_number not in content
        assert "recent active orders" in content

    def test_search_results_are_capped(self, product):
        user = create_user(username="lookup-cap")
        for index in range(55):
            order = create_order(
                user,
                product,
                status=Order.Status.PAID,
                payment_status=Order.PaymentStatus.PAID,
            )
            order.phone = f"0912{index:07d}"
            order.save(update_fields=["phone", "updated_at"])

        results = list(search_orders_queryset("0912"))
        assert len(results) == 50

    def test_default_active_orders_are_capped(self, product):
        user = create_user(username="lookup-default-cap")
        for _ in range(25):
            create_order(
                user,
                product,
                status=Order.Status.PAID,
                payment_status=Order.PaymentStatus.PAID,
            )

        results = list(recent_active_orders_queryset())
        assert len(results) == DEFAULT_LOOKUP_LIMIT
