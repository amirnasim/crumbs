"""Payment callback / verification idempotency."""

import json

import pytest
from django.test import override_settings

from delivery.models import OrderStatusLog
from delivery.services import process_checkout
from inventory.models import StockReservation
from orders.models import Order
from orders.services.order_service import OrderService
from payments.models import Payment, PaymentEvent
from payments.services import PaymentService, handle_zarinpal_callback
from products.services.stock_service import StockService
from tests.factories import CUSTOMER, create_cart_with_item, create_order, create_product, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS, ZARINPAL_INTEGRATION_SETTINGS

ZARINPAL_SETTINGS = ZARINPAL_INTEGRATION_SETTINGS


def _mock_zarinpal_request_and_verify(mocker, authority="A000000000000000000000000000000000", ref_id=123456789):
    mock_request = mocker.Mock()
    mock_request.ok = True
    mock_request.json.return_value = {
        "data": {"code": 100, "authority": authority},
        "errors": [],
    }

    mock_verify = mocker.Mock()
    mock_verify.ok = True
    mock_verify.json.return_value = {
        "data": {"code": 100, "ref_id": ref_id},
        "errors": [],
    }
    mock_verify.raise_for_status = mocker.Mock()

    return mocker.patch(
        "payments.providers.zarinpal.requests.post",
        side_effect=[mock_request, mock_verify],
    )


def _zarinpal_callback_payload(payment: Payment) -> bytes:
    return json.dumps(
        {
            "authority": payment.provider_checkout_session_id,
            "status": "OK",
            "payment_id": payment.pk,
        }
    ).encode("utf-8")


@pytest.mark.django_db
class TestOnlinePaymentCallbackIdempotency:
    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_callback_called_twice_confirms_inventory_once(self, user, product, mocker):
        _mock_zarinpal_request_and_verify(mocker, ref_id=55667788)

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        payment = result.payment
        payload = _zarinpal_callback_payload(payment)

        handle_zarinpal_callback(payload)
        handle_zarinpal_callback(payload)

        order.refresh_from_db()
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert (
            StockReservation.objects.filter(
                order=order,
                status=StockReservation.Status.CONFIRMED,
            ).count()
            == 1
        )
        assert not StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.ACTIVE,
        ).exists()
        assert PaymentEvent.objects.filter(processed=True).count() == 1

    @override_settings(**ZARINPAL_SETTINGS)
    def test_callback_when_payment_already_succeeded_is_noop(self, user, product, mocker):
        _mock_zarinpal_request_and_verify(mocker, ref_id=11223344)

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        payment = result.payment

        PaymentService.mark_paid(order, payment)
        initial_logs = OrderStatusLog.objects.filter(order=order).count()

        handle_zarinpal_callback(_zarinpal_callback_payload(payment))

        order.refresh_from_db()
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert OrderStatusLog.objects.filter(order=order).count() == initial_logs

    @override_settings(**ZARINPAL_SETTINGS)
    def test_callback_when_order_already_paid_before_payment_record_succeeds(self, user, product, mocker):
        _mock_zarinpal_request_and_verify(mocker, ref_id=99881122)

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        payment = result.payment

        OrderService.finalize_online_payment(order)
        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert payment.status == Payment.Status.PROCESSING

        handle_zarinpal_callback(_zarinpal_callback_payload(payment))

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert (
            StockReservation.objects.filter(
                order=order,
                status=StockReservation.Status.CONFIRMED,
            ).count()
            == 1
        )

    @override_settings(**ZARINPAL_SETTINGS)
    def test_failed_callback_does_not_corrupt_paid_order(self, user, product, mocker):
        _mock_zarinpal_request_and_verify(mocker, ref_id=33445566)

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        payment = result.payment

        PaymentService.mark_paid(order, payment)
        order.refresh_from_db()

        failed_payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "NOK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")
        handle_zarinpal_callback(failed_payload)

        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert payment.status == Payment.Status.SUCCEEDED
        assert (
            StockReservation.objects.filter(
                order=order,
                status=StockReservation.Status.CONFIRMED,
            ).count()
            == 1
        )

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_mark_paid_twice_confirms_reservations_once(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        payment = result.payment

        PaymentService.mark_paid(order, payment)
        PaymentService.mark_paid(order, payment)

        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert (
            StockReservation.objects.filter(
                order=order,
                status=StockReservation.Status.CONFIRMED,
            ).count()
            == 1
        )

    def test_finalize_online_payment_is_idempotent(self, user, product):
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        StockService.reserve_for_order(order)

        OrderService.finalize_online_payment(order)
        OrderService.finalize_online_payment(order)

        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert (
            StockReservation.objects.filter(
                order=order,
                status=StockReservation.Status.CONFIRMED,
            ).count()
            == 1
        )
        paid_logs = OrderStatusLog.objects.filter(
            order=order,
            to_status=Order.Status.PAID,
        ).count()
        confirmed_logs = OrderStatusLog.objects.filter(
            order=order,
            to_status=Order.Status.CONFIRMED_BY_SHOP,
        ).count()
        assert paid_logs == 1
        assert confirmed_logs == 1

    def test_mark_failed_ignored_for_paid_order(self, user, product, mocker):
        mocker.patch("orders.services.order_service.StockService.release_reservations")
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PAID,
            status=Order.Status.CONFIRMED_BY_SHOP,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.ZARINPAL,
            status=Payment.Status.SUCCEEDED,
            amount=order.total,
            currency="irr",
        )

        PaymentService.mark_failed(order, payment, "late failure callback")

        order.refresh_from_db()
        payment.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP
        assert payment.status == Payment.Status.SUCCEEDED
