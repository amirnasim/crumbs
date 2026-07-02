"""Staff pickup screen — packaged orders ready for customer collection."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.pickup_views import ACTION_MARK_PICKED_UP, pickup_screen_queryset
from orders.models import Order
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="pickup-staff",
        email="pickup-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


def _pickup_action_url():
    return reverse("admin:crumbs_pickup_action")


@pytest.mark.django_db
class TestPickupScreenAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/pickup-screen/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/pickup-screen/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_staff_user_can_view_pickup_screen(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/pickup-screen/")

        assert response.status_code == 200
        assert b"Pickup Screen" in response.content


@pytest.mark.django_db
class TestPickupScreenOrders:
    def test_only_packaged_paid_orders_are_listed(self, client, staff_user, product):
        user = create_user(username="pickup-guest")
        ready = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        ready.notes = "Table 5"
        ready.save(update_fields=["notes"])
        create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )
        create_order(
            user,
            product,
            status=Order.Status.AWAITING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.CASH,
        )

        queryset = pickup_screen_queryset()
        assert queryset.count() == 1
        assert queryset.first().pk == ready.pk

        client.force_login(staff_user)
        response = client.get("/admin/pickup-screen/")

        content = response.content.decode()
        assert response.status_code == 200
        assert ready.order_number in content
        assert ready.first_name in content
        assert "Table 5" in content

    def test_mark_picked_up_completes_order(self, client, staff_user, product):
        user = create_user(username="complete-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        client.force_login(staff_user)
        response = client.post(
            _pickup_action_url(),
            data={"order_id": order.pk, "action": ACTION_MARK_PICKED_UP},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.DELIVERED

    def test_preparing_order_not_in_pickup_action_queryset(self, client, staff_user, product):
        user = create_user(username="not-ready")
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.post(
            _pickup_action_url(),
            data={"order_id": order.pk, "action": ACTION_MARK_PICKED_UP},
        )

        assert response.status_code == 404
        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING

    def test_get_action_is_not_allowed(self, client, staff_user, product):
        user = create_user(username="get-pickup")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.get(
            _pickup_action_url(),
            data={"order_id": order.pk, "action": ACTION_MARK_PICKED_UP},
        )

        assert response.status_code == 405
