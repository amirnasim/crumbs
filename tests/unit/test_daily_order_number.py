"""Tests for daily short order numbers and receipt view."""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone

from orders.daily_sequence import DAILY_SEQUENCE_START, assign_daily_sequence
from orders.models import Order
from tests.factories import create_order, create_user

User = get_user_model()


@pytest.mark.django_db
class TestDailySequenceAssignment:
    def test_first_order_of_day_gets_101(self, product):
        user = create_user()
        order = create_order(user, product)
        assert order.daily_sequence == DAILY_SEQUENCE_START
        assert order.display_number == "#101"
        assert order.daily_sequence_date == timezone.localdate(order.created_at)

    def test_sequential_numbers_same_day(self, product):
        user = create_user()
        first = create_order(user, product)
        second = create_order(user, product)
        assert first.daily_sequence == 101
        assert second.daily_sequence == 102

    def test_order_number_unchanged_after_assignment(self, product):
        user = create_user()
        order = Order.objects.create(
            order_number="CR-KEEP-ME-001",
            user=user,
            email=user.email,
            phone="09121234567",
            first_name="Ali",
            last_name="Rezaei",
            payment_method=Order.PaymentMethod.CASH,
            delivery_type=Order.DeliveryType.PICKUP,
            payment_status=Order.PaymentStatus.PAID,
            status=Order.Status.PAID,
            subtotal=product.price,
            total=product.price,
        )
        assign_daily_sequence(order)
        order.refresh_from_db()
        assert order.order_number == "CR-KEEP-ME-001"
        assert order.daily_sequence == 101

    def test_idempotent_assignment(self, product):
        user = create_user()
        order = create_order(user, product)
        original_sequence = order.daily_sequence
        assign_daily_sequence(order)
        order.refresh_from_db()
        assert order.daily_sequence == original_sequence


@pytest.mark.django_db
class TestDailyNumberInViews:
    def test_confirmation_shows_display_number(self, client, product):
        user = create_user()
        order = create_order(user, product)
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(reverse("core:order_confirmation", args=[order.order_number]))
        content = response.content.decode()

        assert response.status_code == 200
        assert "#101" in content
        assert order.order_number in content

    def test_kitchen_queue_shows_display_number(self, client, product):
        staff = User.objects.create_user(
            username="kitchen-staff",
            email="kitchen@example.com",
            password="pass12345",
            is_staff=True,
        )
        user = create_user()
        create_order(user, product, status=Order.Status.PAID)

        client.force_login(staff)
        response = client.get(reverse("admin:crumbs_kitchen"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "#101" in content

    def test_pickup_screen_shows_display_number(self, client, product):
        staff = User.objects.create_user(
            username="pickup-staff",
            email="pickup@example.com",
            password="pass12345",
            is_staff=True,
        )
        user = create_user()
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
        )

        client.force_login(staff)
        response = client.get(reverse("admin:crumbs_pickup_screen"))
        content = response.content.decode()

        assert response.status_code == 200
        assert "#101" in content
        assert order.order_number in content


@pytest.mark.django_db
class TestOrderReceiptView:
    def _receipt_url(self, order_number: str) -> str:
        return reverse("core:order_receipt", args=[order_number])

    def test_anonymous_without_session_denied(self, client, product):
        user = create_user()
        order = create_order(user, product)
        response = client.get(self._receipt_url(order.order_number))
        assert response.status_code == 302
        assert "login" in response.url

    def test_guest_with_checkout_session_can_view(self, client, product):
        user = create_user()
        order = create_order(user, product)
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(self._receipt_url(order.order_number))
        content = response.content.decode()

        assert response.status_code == 200
        assert "#101" in content
        assert order.order_number in content

    def test_owner_can_view_receipt(self, client, product):
        user = create_user()
        order = create_order(user, product)
        client.force_login(user)

        response = client.get(self._receipt_url(order.order_number))
        assert response.status_code == 200

    def test_staff_can_view_receipt(self, client, product):
        staff = User.objects.create_user(
            username="receipt-staff",
            email="receipt@example.com",
            password="pass12345",
            is_staff=True,
        )
        user = create_user()
        order = create_order(user, product)
        client.force_login(staff)

        response = client.get(self._receipt_url(order.order_number))
        content = response.content.decode()

        assert response.status_code == 200
        assert order.order_number in content
