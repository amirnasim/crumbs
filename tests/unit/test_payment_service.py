"""Unit tests for PaymentService."""

import json
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.test import override_settings

from orders.models import Order
from orders.services.order_service import OrderService
from payments.exceptions import PaymentConfigurationError, PaymentError, PaymentProviderError
from payments.models import Payment
from payments.services import PaymentService, handle_zarinpal_callback, process_webhook
from tests.factories import create_order, create_product, create_user
from tests.mocks.payments import MockPaymentProvider

ZARINPAL_SETTINGS = {
    "DEFAULT_PAYMENT_PROVIDER": "zarinpal",
    "PAYMENT_PROVIDER": "zarinpal",
    "ZARINPAL_MERCHANT_ID": "test-merchant-id",
    "ZARINPAL_SANDBOX": True,
    "ZARINPAL_CALLBACK_URL": "https://example.com/payments/zarinpal/callback/",
    "ONLINE_PAYMENT_CURRENCY": "irr",
}


def _mock_zarinpal_request(mocker, authority="A000000000000000000000000000000000"):
    mock_response = mocker.Mock()
    mock_response.ok = True
    mock_response.json.return_value = {
        "data": {"code": 100, "authority": authority},
        "errors": [],
    }
    return mocker.patch(
        "payments.providers.zarinpal.requests.post",
        return_value=mock_response,
    )


def _mock_zarinpal_http_error(
    mocker,
    *,
    status_code=422,
    body=None,
    text="",
    content_type="application/json",
):
    mock_response = mocker.Mock()
    mock_response.ok = False
    mock_response.status_code = status_code
    mock_response.headers = {"Content-Type": content_type}
    if body is not None:
        mock_response.json.return_value = body
        mock_response.text = json.dumps(body)
    else:
        mock_response.text = text
        mock_response.json.side_effect = ValueError("not json")
    return mocker.patch(
        "payments.providers.zarinpal.requests.post",
        return_value=mock_response,
    )


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


@pytest.mark.django_db
class TestPaymentService:
    @override_settings(DEFAULT_PAYMENT_METHOD="cod")
    def test_initiate_cod_creates_pending_payment(self):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.COD,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_cod(order)
        assert payment.provider == Payment.Provider.COD
        assert payment.status == Payment.Status.PENDING
        assert payment.amount == order.total

    @override_settings(
        DEFAULT_PAYMENT_PROVIDER="stripe",
        PAYMENT_PROVIDER="stripe",
        STRIPE_ENABLED=True,
    )
    def test_initiate_online_requires_stripe_mock(self, mock_stripe_checkout):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_online(order)
        assert payment.status == Payment.Status.PROCESSING
        assert payment.checkout_url == "https://checkout.stripe.com/test"
        mock_stripe_checkout.assert_called_once()

    @override_settings(
        DEFAULT_PAYMENT_PROVIDER="stripe",
        PAYMENT_PROVIDER="stripe",
        STRIPE_ENABLED=False,
    )
    def test_stripe_checkout_blocked_when_disabled(self):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        with pytest.raises(PaymentConfigurationError, match="Stripe checkout is disabled"):
            PaymentService.initiate_online(order)

    @override_settings(**ZARINPAL_SETTINGS)
    def test_initiate_online_uses_zarinpal(self, mocker):
        mock_post = _mock_zarinpal_request(mocker)

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_online(order)

        assert payment.provider == Payment.Provider.ZARINPAL
        assert payment.status == Payment.Status.PROCESSING
        assert payment.currency == "irr"
        assert payment.amount == order.total
        assert payment.checkout_url.endswith("A000000000000000000000000000000000")
        assert payment.provider_checkout_session_id == "A000000000000000000000000000000000"
        mock_post.assert_called_once()
        request_payload = mock_post.call_args.kwargs["json"]
        assert request_payload["amount"] == int(order.total)

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_duplicate_request_returns_existing_payment(self, mocker):
        mock_post = _mock_zarinpal_request(mocker)

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )

        first = PaymentService.initiate_online(order)
        second = PaymentService.initiate_online(order)

        assert first.pk == second.pk
        assert second.checkout_url == first.checkout_url
        assert second.provider_checkout_session_id == first.provider_checkout_session_id
        mock_post.assert_called_once()

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_amount_uses_final_order_total_with_discount(self, mocker):
        mock_post = _mock_zarinpal_request(mocker)

        user = create_user()
        product = create_product(price=Decimal("200000"))
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
            discount_amount=Decimal("25000"),
        )

        payment = PaymentService.initiate_online(order)

        assert payment.amount == order.total
        assert order.total == Decimal("200000") - Decimal("25000")
        assert mock_post.call_args.kwargs["json"]["amount"] == int(order.total)

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_http_error_includes_response_body(self, mocker):
        error_body = {
            "data": {},
            "errors": {
                "callback_url": ["The callback url format is invalid."],
                "merchant_id": ["test-merchant-id"],
            },
        }
        mock_post = _mock_zarinpal_http_error(mocker, status_code=422, body=error_body)
        log_error = mocker.patch("payments.providers.zarinpal.logger.error")

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )

        with pytest.raises(PaymentProviderError, match=r"HTTP 422") as exc_info:
            PaymentService.initiate_online(order)

        message = str(exc_info.value)
        assert "callback url format is invalid" in message.lower()
        assert "test-merchant-id" not in message
        assert "***" in message
        mock_post.assert_called_once()
        log_error.assert_called_once()
        debug = log_error.call_args.kwargs["extra"]
        assert debug["status_code"] == 422
        assert debug["amount"] == int(order.total)
        assert debug["callback_url"] == ZARINPAL_SETTINGS["ZARINPAL_CALLBACK_URL"]
        assert debug["description_length"] > 0
        assert debug["endpoint"] == "https://sandbox.zarinpal.com/pg/v4/payment/request.json"
        assert debug["sandbox"] is True
        assert debug["merchant_id_configured"] is True
        assert "test-merchant-id" not in str(debug)

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_successful_callback_verifies_and_marks_paid(self, mocker):
        mock_post = _mock_zarinpal_request_and_verify(mocker, ref_id=99887766)
        finalize = mocker.patch.object(OrderService, "finalize_online_payment")

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_online(order)

        payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "OK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")
        event = handle_zarinpal_callback(payload)

        payment.refresh_from_db()
        order.refresh_from_db()
        assert event.processed is True
        assert payment.status == Payment.Status.SUCCEEDED
        assert payment.provider_payment_id == "99887766"
        assert payment.metadata["zarinpal_ref_id"] == 99887766
        assert finalize.call_count == 1
        assert mock_post.call_count == 2

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_failed_callback_marks_failed(self, mocker):
        mock_post = _mock_zarinpal_request(mocker)
        mocker.patch("orders.services.order_service.StockService.release_reservations")

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_online(order)

        payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "NOK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")
        handle_zarinpal_callback(payload)

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == Payment.Status.FAILED
        assert order.payment_status == Order.PaymentStatus.FAILED
        assert order.status == Order.Status.CANCELLED
        assert mock_post.call_count == 1

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_duplicate_callback_is_idempotent(self, mocker):
        mock_post = _mock_zarinpal_request_and_verify(mocker, ref_id=44556677)
        finalize = mocker.patch.object(OrderService, "finalize_online_payment")

        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = PaymentService.initiate_online(order)

        payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "OK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")

        handle_zarinpal_callback(payload)
        handle_zarinpal_callback(payload)

        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert finalize.call_count == 1
        assert mock_post.call_count == 2

    def test_mark_paid_is_idempotent(self, mocker):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.STRIPE,
            status=Payment.Status.PROCESSING,
            amount=order.total,
            currency="irr",
        )
        finalize = mocker.patch.object(OrderService, "finalize_online_payment")
        PaymentService.mark_paid(order, payment)
        PaymentService.mark_paid(order, payment)
        payment.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert finalize.call_count == 1

    def test_mark_failed_cancels_order(self, mocker):
        user = create_user()
        product = create_product()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.ONLINE,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
        )
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.STRIPE,
            status=Payment.Status.PROCESSING,
            amount=order.total,
            currency="irr",
        )
        mocker.patch("orders.services.order_service.StockService.release_reservations")
        PaymentService.mark_failed(order, payment, "card declined")
        order.refresh_from_db()
        payment.refresh_from_db()
        assert payment.status == Payment.Status.FAILED
        assert order.status == Order.Status.CANCELLED

    def test_mark_paid_on_already_paid_order_raises(self):
        user = create_user()
        product = create_product()
        order = create_order(user, product, payment_status=Order.PaymentStatus.PAID, status=Order.Status.PAID)
        payment = Payment.objects.create(
            order=order,
            provider=Payment.Provider.STRIPE,
            status=Payment.Status.PENDING,
            amount=order.total,
            currency="irr",
        )
        with pytest.raises(PaymentError):
            PaymentService.initiate_online(order)

    def test_duplicate_webhook_not_reprocessed(self):
        provider = MockPaymentProvider()
        event = provider.verify_webhook(b"{}", "sig")
        with patch.object(provider, "handle_webhook_event") as handler:
            process_webhook(provider, b"{}", "sig")
            process_webhook(provider, b"{}", "sig")
            assert handler.call_count == 1
