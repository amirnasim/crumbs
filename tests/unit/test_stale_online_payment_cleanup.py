"""Stale unpaid online payment cleanup."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from cart.models import Cart
from delivery.models import OrderStatusLog
from inventory.models import ProductInventory, StockReservation
from orders.models import Order
from payments.models import Payment
from payments.stale_cleanup import (
    STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES,
    cleanup_stale_online_payment,
    cleanup_stale_online_payments,
    stale_online_payments_queryset,
)
from payments.tasks import cleanup_stale_online_payments_task
from products.services.stock_service import StockService
from tests.factories import create_cart_with_item, create_order, create_product, create_user

User = get_user_model()

ZARINPAL_OPS_SETTINGS = {
    "DEFAULT_PAYMENT_PROVIDER": "zarinpal",
    "PAYMENT_PROVIDER": "zarinpal",
    "ZARINPAL_MERCHANT_ID": "00000000-0000-0000-0000-000000000001",
    "ZARINPAL_SANDBOX": True,
    "ZARINPAL_CALLBACK_URL": "https://example.com/payments/zarinpal/callback/",
    "DEFAULT_PAYMENT_METHOD": "online",
    "ONLINE_PAYMENT_CURRENCY": "irr",
}


def _create_stale_online_checkout(user, product, *, minutes_ago=45):
    order = create_order(
        user,
        product,
        status=Order.Status.PENDING_PAYMENT,
        payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        payment_method=Order.PaymentMethod.ONLINE,
    )
    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.ZARINPAL,
        status=Payment.Status.PENDING,
        amount=order.total,
    )
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timedelta(minutes=minutes_ago),
    )
    payment.refresh_from_db()
    StockService.reserve_for_order(order)
    return order, payment


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="stale-cleanup-staff",
        email="stale-cleanup-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestStaleOnlinePaymentCleanup:
    def test_stale_unpaid_online_order_releases_stock(self, user, product):
        order, payment = _create_stale_online_checkout(user, product)
        inventory = ProductInventory.objects.get(product=product)
        reserved_before = inventory.reserved_quantity

        result = cleanup_stale_online_payments()

        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()
        reservation = StockReservation.objects.get(order=order)

        assert result["cleaned"] == 1
        assert payment.status == Payment.Status.FAILED
        assert order.status == Order.Status.CANCELLED
        assert order.payment_status == Order.PaymentStatus.FAILED
        assert reservation.status == StockReservation.Status.RELEASED
        assert inventory.reserved_quantity == reserved_before - 1
        assert OrderStatusLog.objects.filter(order=order, to_status=Order.Status.CANCELLED).exists()

    def test_fresh_pending_payment_is_ignored(self, user, product):
        order, payment = _create_stale_online_checkout(user, product, minutes_ago=10)
        inventory = ProductInventory.objects.get(product=product)
        reserved_before = inventory.reserved_quantity

        result = cleanup_stale_online_payments()

        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert result["cleaned"] == 0
        assert payment.status == Payment.Status.PENDING
        assert order.status == Order.Status.PENDING_PAYMENT
        assert inventory.reserved_quantity == reserved_before
        assert StockReservation.objects.get(order=order).status == StockReservation.Status.ACTIVE

    def test_paid_order_is_ignored_even_if_payment_row_is_old_and_pending(self, user, product):
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.ZARINPAL,
            status=Payment.Status.PENDING,
            amount=order.total,
        )
        Payment.objects.filter(pk=payment.pk).update(
            created_at=timezone.now() - timedelta(minutes=45),
        )

        result = cleanup_stale_online_payments()

        order.refresh_from_db()
        payment.refresh_from_db()

        assert result["cleaned"] == 0
        assert payment.status == Payment.Status.PENDING
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP

    def test_running_cleanup_twice_is_safe(self, user, product):
        order, payment = _create_stale_online_checkout(user, product)
        inventory = ProductInventory.objects.get(product=product)

        first = cleanup_stale_online_payments()
        reserved_after_first = ProductInventory.objects.get(product=product).reserved_quantity
        second = cleanup_stale_online_payments()

        order.refresh_from_db()
        payment.refresh_from_db()
        inventory.refresh_from_db()

        assert first["cleaned"] == 1
        assert second["cleaned"] == 0
        assert payment.status == Payment.Status.FAILED
        assert order.status == Order.Status.CANCELLED
        assert inventory.reserved_quantity == reserved_after_first
        assert StockReservation.objects.get(order=order).status == StockReservation.Status.RELEASED

    def test_released_reservations_are_not_double_released(self, user, product):
        order, payment = _create_stale_online_checkout(user, product)
        StockService.release_reservations(order)
        inventory = ProductInventory.objects.get(product=product)
        reserved_before = inventory.reserved_quantity

        outcome = cleanup_stale_online_payment(payment.pk)

        inventory.refresh_from_db()
        assert outcome == "cleaned"
        assert inventory.reserved_quantity == reserved_before

    def test_clears_cart_active_checkout_order(self, user, product):
        order, payment = _create_stale_online_checkout(user, product)
        cart = create_cart_with_item(user, product)
        cart.active_checkout_order = order
        cart.save(update_fields=["active_checkout_order", "updated_at"])

        cleanup_stale_online_payments()

        cart.refresh_from_db()
        assert cart.active_checkout_order_id is None

    @override_settings(**ZARINPAL_OPS_SETTINGS)
    def test_ops_dashboard_stale_payment_visibility_after_cleanup(self, client, staff_user, user, product):
        stale_order, stale_payment = _create_stale_online_checkout(user, product)
        paid_with_stale_payment = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        old_pending_on_paid = Payment.objects.create(
            order=paid_with_stale_payment,
            provider=Payment.Provider.ZARINPAL,
            status=Payment.Status.PENDING,
            amount=paid_with_stale_payment.total,
        )
        Payment.objects.filter(pk=old_pending_on_paid.pk).update(
            created_at=timezone.now() - timedelta(minutes=45),
        )

        client.force_login(staff_user)
        before = client.get("/admin/ops/")
        assert before.status_code == 200
        assert before.context["counts"]["stale_online_payments"] == 2

        cleanup_stale_online_payments()

        after = client.get("/admin/ops/")
        assert after.status_code == 200
        assert after.context["counts"]["stale_online_payments"] == 1
        assert after.context["counts"]["failed_payments"] >= 1
        stale_order.refresh_from_db()
        stale_payment.refresh_from_db()
        assert stale_order.status == Order.Status.CANCELLED
        assert stale_payment.status == Payment.Status.FAILED
        assert paid_with_stale_payment.payment_status == Order.PaymentStatus.PAID

    def test_cleanup_task_survives_single_order_failure(self, user, product):
        order, payment = _create_stale_online_checkout(user, product)
        other_order, other_payment = _create_stale_online_checkout(
            create_user(username="other-buyer"),
            create_product(name="Other Cookie", stock_quantity=5),
        )

        original = cleanup_stale_online_payment

        def flaky_cleanup(payment_id):
            if payment_id == payment.pk:
                raise RuntimeError("simulated worker error")
            return original(payment_id)

        with patch("payments.stale_cleanup.cleanup_stale_online_payment", side_effect=flaky_cleanup):
            result = cleanup_stale_online_payments_task()

        order.refresh_from_db()
        other_order.refresh_from_db()
        assert result["errors"] == 1
        assert result["cleaned"] == 1
        assert order.status == Order.Status.PENDING_PAYMENT
        assert other_order.status == Order.Status.CANCELLED

    def test_stale_queryset_uses_configured_timeout(self, user, product):
        _create_stale_online_checkout(user, product, minutes_ago=45)
        _create_stale_online_checkout(
            create_user(username="fresh-buyer"),
            product,
            minutes_ago=10,
        )

        stale_ids = set(stale_online_payments_queryset().values_list("pk", flat=True))
        assert len(stale_ids) == 1
        assert STALE_ONLINE_PAYMENT_TIMEOUT_MINUTES == 30
