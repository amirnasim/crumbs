"""Kitchen queue — staff-only in-cafe order preparation screen."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from core.kitchen_views import (
    ACTION_MARK_COMPLETED,
    ACTION_MARK_READY,
    ACTION_START_PREPARING,
    kitchen_order_queryset,
)
from orders.models import Order
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="kitchen-staff",
        email="kitchen-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


def _kitchen_action_url():
    return reverse("admin:crumbs_kitchen_action")


@pytest.mark.django_db
class TestKitchenQueueAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/kitchen/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/kitchen/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_staff_user_can_view_kitchen_queue(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/kitchen/")

        assert response.status_code == 200
        assert b"Kitchen Queue" in response.content


@pytest.mark.django_db
class TestKitchenQueueOrders:
    def test_staff_sees_active_paid_preparing_and_ready_orders(self, client, staff_user, product):
        user = create_user(username="cafe-guest")
        waiting = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        preparing = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.CASH,
        )
        ready = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.COUNTER_CARD,
        )
        ready.notes = "میز ۳"
        ready.save(update_fields=["notes", "updated_at"])

        client.force_login(staff_user)
        response = client.get("/admin/kitchen/")

        assert response.status_code == 200
        assert waiting.order_number.encode() in response.content
        assert preparing.order_number.encode() in response.content
        assert ready.order_number.encode() in response.content
        assert "میز ۳".encode() in response.content
        assert response.context["counts"]["waiting"] == 1
        assert response.context["counts"]["preparing"] == 1
        assert response.context["counts"]["ready"] == 1

    def test_awaiting_payment_orders_excluded(self, client, staff_user, product):
        user = create_user(username="awaiting-guest")
        awaiting = create_order(
            user,
            product,
            status=Order.Status.AWAITING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.CASH,
        )
        create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        client.force_login(staff_user)
        response = client.get("/admin/kitchen/")

        assert response.status_code == 200
        assert awaiting.order_number.encode() not in response.content
        assert kitchen_order_queryset().filter(pk=awaiting.pk).exists() is False

    def test_cancelled_orders_excluded(self, client, staff_user, product):
        user = create_user(username="cancelled-guest")
        cancelled = create_order(
            user,
            product,
            status=Order.Status.CANCELLED,
            payment_status=Order.PaymentStatus.FAILED,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        assert kitchen_order_queryset().filter(pk=cancelled.pk).exists() is False

        client.force_login(staff_user)
        response = client.get("/admin/kitchen/")

        assert cancelled.order_number.encode() not in response.content


@pytest.mark.django_db
class TestKitchenQueueActions:
    def test_start_preparing_action(self, client, staff_user, product):
        user = create_user(username="prep-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        client.force_login(staff_user)
        response = client.post(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_START_PREPARING},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING

    def test_mark_ready_action(self, client, staff_user, product):
        user = create_user(username="ready-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.CASH,
        )

        client.force_login(staff_user)
        response = client.post(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_MARK_READY},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.PACKAGED

    def test_mark_completed_action(self, client, staff_user, product):
        from inventory.models import ProductInventory, StockReservation
        from django.utils import timezone

        user = create_user(username="done-guest")
        product = create_product(stock_quantity=10)
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        StockReservation.objects.create(
            product=product,
            order=order,
            quantity=1,
            production_date=timezone.localdate(),
            status=StockReservation.Status.CONFIRMED,
        )
        inventory = ProductInventory.objects.get(product=product)
        inventory.reserved_quantity = 1
        inventory.save(update_fields=["reserved_quantity", "updated_at"])

        client.force_login(staff_user)
        response = client.post(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_MARK_COMPLETED},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.DELIVERED

    def test_invalid_action_does_not_corrupt_order(self, client, staff_user, product):
        user = create_user(username="invalid-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        client.force_login(staff_user)
        response = client.post(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_START_PREPARING},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.PACKAGED

    def test_get_action_is_not_allowed(self, client, staff_user, product):
        user = create_user(username="get-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.get(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_START_PREPARING},
        )

        assert response.status_code == 405
        order.refresh_from_db()
        assert order.status == Order.Status.CONFIRMED_BY_SHOP

    def test_duplicate_start_preparing_is_idempotent(self, client, staff_user, product):
        user = create_user(username="dup-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff_user)
        response = client.post(
            _kitchen_action_url(),
            data={"order_id": order.pk, "action": ACTION_START_PREPARING},
        )

        assert response.status_code == 302
        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING
