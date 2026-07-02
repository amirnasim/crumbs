"""Tests for Django admin order lifecycle actions."""

import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import RequestFactory
from django.utils import timezone

from inventory.models import DailyProductionCapacity, ProductInventory, StockReservation
from orders.admin import OrderAdmin
from orders.models import Order
from payments.models import Payment
from payments.services import PaymentService
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def rf():
    return RequestFactory()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="order-admin",
        email="order-admin@example.com",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def order_admin():
    return OrderAdmin(Order, admin.site)


def _admin_request(rf, user):
    request = rf.post("/admin/orders/order/")
    request.user = user
    middleware = SessionMiddleware(lambda req: HttpResponse())
    middleware.process_request(request)
    request.session.save()
    request._messages = FallbackStorage(request)
    return request


def _message_texts(request):
    return [str(message) for message in request._messages]


def _cod_order_with_payment(*, status=Order.Status.OUT_FOR_DELIVERY):
    user = create_user(username="cod-customer")
    product = create_product(stock_quantity=20)
    order = create_order(
        user,
        product,
        status=status,
        payment_status=Order.PaymentStatus.COD_CONFIRMED,
        payment_method=Order.PaymentMethod.COD,
    )
    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.COD,
        status=Payment.Status.PENDING,
        amount=order.total,
        currency="irr",
    )
    production_date = timezone.localdate()
    DailyProductionCapacity.objects.create(
        product=product,
        production_date=production_date,
        max_units=50,
    )
    StockReservation.objects.create(
        product=product,
        order=order,
        quantity=1,
        production_date=production_date,
        status=StockReservation.Status.CONFIRMED,
    )
    inventory = ProductInventory.objects.get(product=product)
    inventory.reserved_quantity = 1
    inventory.save(update_fields=["reserved_quantity", "updated_at"])
    return order, payment, inventory


@pytest.mark.django_db
class TestOrderAdminLifecycleActions:
    def test_mark_as_preparing_transitions_confirmed_order(
        self, rf, staff_user, order_admin
    ):
        user = create_user(username="lifecycle-user")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        request = _admin_request(rf, staff_user)

        order_admin.advance_to_preparing(request, Order.objects.filter(pk=order.pk))

        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING
        assert any("Marked 1 order(s) as preparing." in text for text in _message_texts(request))

    def test_mark_as_preparing_is_idempotent(self, rf, staff_user, order_admin):
        user = create_user(username="idempotent-user")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        request = _admin_request(rf, staff_user)

        order_admin.advance_to_preparing(request, Order.objects.filter(pk=order.pk))

        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING
        assert any("already preparing" in text for text in _message_texts(request))

    def test_mark_as_packaged_and_out_for_delivery(self, rf, staff_user, order_admin):
        user = create_user(username="delivery-user")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        request = _admin_request(rf, staff_user)
        queryset = Order.objects.filter(pk=order.pk)

        order_admin.advance_to_packaged(request, queryset)
        order.refresh_from_db()
        assert order.status == Order.Status.PACKAGED

        order_admin.advance_to_out_for_delivery(request, queryset)
        order.refresh_from_db()
        assert order.status == Order.Status.OUT_FOR_DELIVERY

    def test_mark_as_delivered_for_paid_online_order(self, rf, staff_user, order_admin):
        user = create_user(username="online-delivered")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.OUT_FOR_DELIVERY,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        request = _admin_request(rf, staff_user)

        order_admin.mark_delivered(request, Order.objects.filter(pk=order.pk))

        order.refresh_from_db()
        assert order.status == Order.Status.DELIVERED
        assert any("Marked 1 order(s) as picked up." in text for text in _message_texts(request))

    def test_mark_as_delivered_cod_without_cash_reports_failure(
        self, rf, staff_user, order_admin
    ):
        order, payment, _inventory = _cod_order_with_payment()
        request = _admin_request(rf, staff_user)

        order_admin.mark_delivered(request, Order.objects.filter(pk=order.pk))

        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.status == Order.Status.OUT_FOR_DELIVERY
        assert payment.status == Payment.Status.PENDING
        assert any("COD orders require cash received" in text for text in _message_texts(request))

    def test_mark_cod_cash_received_finalizes_payment_and_inventory(
        self, rf, staff_user, order_admin
    ):
        order, payment, inventory = _cod_order_with_payment()
        initial_stock = inventory.stock_quantity
        request = _admin_request(rf, staff_user)

        order_admin.mark_cod_cash_received(request, Order.objects.filter(pk=order.pk))

        payment.refresh_from_db()
        order.refresh_from_db()
        inventory.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert order.payment_status == Order.PaymentStatus.CASH_RECEIVED
        assert order.status == Order.Status.DELIVERED
        assert inventory.stock_quantity == initial_stock - 1
        assert inventory.reserved_quantity == 0
        assert any("Recorded COD cash for 1 order(s)." in text for text in _message_texts(request))

    def test_mark_cod_cash_received_is_idempotent(self, rf, staff_user, order_admin):
        order, payment, inventory = _cod_order_with_payment()
        request = _admin_request(rf, staff_user)
        queryset = Order.objects.filter(pk=order.pk)

        order_admin.mark_cod_cash_received(request, queryset)
        inventory.refresh_from_db()
        stock_after_first = inventory.stock_quantity

        order_admin.mark_cod_cash_received(request, queryset)
        inventory.refresh_from_db()
        payment.refresh_from_db()

        assert payment.status == Payment.Status.SUCCEEDED
        assert inventory.stock_quantity == stock_after_first
        assert any("COD cash already recorded." in text for text in _message_texts(request))

    def test_invalid_transition_reports_admin_error(self, rf, staff_user, order_admin):
        user = create_user(username="invalid-transition")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        request = _admin_request(rf, staff_user)

        order_admin.advance_to_preparing(request, Order.objects.filter(pk=order.pk))

        order.refresh_from_db()
        assert order.status == Order.Status.PENDING_PAYMENT
        assert any("Cannot transition order" in text for text in _message_texts(request))

    def test_mark_cod_cash_received_without_payment_record_reports_error(
        self, rf, staff_user, order_admin
    ):
        user = create_user(username="no-payment")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.OUT_FOR_DELIVERY,
            payment_status=Order.PaymentStatus.COD_CONFIRMED,
            payment_method=Order.PaymentMethod.COD,
        )
        request = _admin_request(rf, staff_user)

        order_admin.mark_cod_cash_received(request, Order.objects.filter(pk=order.pk))

        assert any("No COD payment record found." in text for text in _message_texts(request))

    def test_admin_actions_use_payment_service_not_raw_status_writes(
        self, rf, staff_user, order_admin, mocker
    ):
        order, payment, _inventory = _cod_order_with_payment()
        spy = mocker.spy(PaymentService, "mark_cod_cash_received")
        request = _admin_request(rf, staff_user)

        order_admin.mark_cod_cash_received(request, Order.objects.filter(pk=order.pk))

        spy.assert_called_once()
