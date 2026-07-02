"""Flow B: Cart → Checkout → Payment failed → retry → success → completed."""

import json
from decimal import Decimal

import pytest
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import reverse

from delivery.services import ONLINE_PAYMENT_UNAVAILABLE_MESSAGE, process_checkout
from inventory.models import ProductInventory
from orders.exceptions import CheckoutError
from orders.models import Order
from payments.models import Payment
from payments.services import PaymentService, handle_zarinpal_callback
from tests.factories import CUSTOMER, create_cart_with_item, create_product
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS, ZARINPAL_INTEGRATION_SETTINGS

ZARINPAL_SETTINGS = ZARINPAL_INTEGRATION_SETTINGS


def _mock_zarinpal_http_error(mocker, *, status_code=422, body=None):
    mock_response = mocker.Mock()
    mock_response.ok = False
    mock_response.status_code = status_code
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.json.return_value = body or {
        "data": {},
        "errors": {"callback_url": ["The callback url format is invalid."]},
    }
    mock_response.text = json.dumps(mock_response.json.return_value)
    return mocker.patch(
        "payments.providers.zarinpal.requests.post",
        return_value=mock_response,
    )


def _mock_zarinpal_success(mocker, authority="A000000000000000000000000000000000"):
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


@pytest.mark.integration
@pytest.mark.django_db
class TestOnlinePaymentFlow:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_pickup_checkout_without_delivery_address(self, user, product, mock_stripe_checkout):
        from inventory.models import StockReservation

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order

        assert order.payment_method == Order.PaymentMethod.ONLINE
        assert order.delivery_type == Order.DeliveryType.PICKUP
        assert order.delivery_fee == Decimal("0.00")
        assert order.delivery_zone_id is None
        assert order.address_line1 == ""
        assert order.city == ""
        assert order.total == order.subtotal
        assert result.checkout_url is not None
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.ACTIVE,
        ).exists()

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_payment_finalizes_inventory_on_success(self, user, product, mock_stripe_checkout):
        from inventory.models import ProductInventory, StockReservation

        cart = create_cart_with_item(user, product)
        inventory = ProductInventory.objects.get(product=product)
        initial_stock = inventory.stock_quantity

        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order
        inventory.refresh_from_db()
        assert inventory.reserved_quantity >= 1
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.ACTIVE,
        ).exists()

        PaymentService.mark_paid(order, result.payment)
        order.refresh_from_db()
        inventory.refresh_from_db()

        assert order.payment_status == Order.PaymentStatus.PAID
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.CONFIRMED,
        ).exists()
        assert inventory.stock_quantity == initial_stock
        assert inventory.reserved_quantity >= 1

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_payment_failed_then_retry_success(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product)
        first = process_checkout(cart, CUSTOMER, user=user)
        order = first.order
        payment = first.payment

        assert order.status == Order.Status.PENDING_PAYMENT
        assert payment.status == Payment.Status.PROCESSING

        PaymentService.mark_failed(order, payment, "card declined")
        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED
        assert order.payment_status == Order.PaymentStatus.FAILED

        product2 = create_product(name="Retry Cookie", price=Decimal("120000"))
        cart2 = create_cart_with_item(user, product2)
        second = process_checkout(cart2, CUSTOMER, user=user)
        order2 = second.order
        payment2 = second.payment

        PaymentService.mark_paid(order2, payment2)
        order2.refresh_from_db()
        assert order2.payment_status == Order.PaymentStatus.PAID
        assert order2.status == Order.Status.CONFIRMED_BY_SHOP

    @override_settings(**{**ZARINPAL_SETTINGS, "DEFAULT_PAYMENT_METHOD": "online"})
    def test_provider_error_does_not_raise_500(self, user, product, mocker):
        _mock_zarinpal_http_error(mocker)

        cart = create_cart_with_item(user, product)
        with pytest.raises(CheckoutError, match="پرداخت آنلاین"):
            process_checkout(cart, CUSTOMER, user=user)

        cart.refresh_from_db()
        assert cart.active_checkout_order_id is None
        assert cart.items.count() == 1
        assert Order.objects.filter(user=user).count() == 0

    @override_settings(**{**ZARINPAL_SETTINGS, "DEFAULT_PAYMENT_METHOD": "online"})
    def test_provider_error_releases_stock_and_allows_retry(self, user, product, mocker):
        cart = create_cart_with_item(user, product)
        inventory = ProductInventory.objects.get(product=product)
        reserved_after_cart_add = inventory.reserved_quantity
        _mock_zarinpal_http_error(mocker)

        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)

        inventory.refresh_from_db()
        assert inventory.reserved_quantity == reserved_after_cart_add

        _mock_zarinpal_success(mocker)
        result = process_checkout(cart, CUSTOMER, user=user)
        assert Order.objects.filter(user=user).count() == 1
        assert result.payment.status == Payment.Status.PROCESSING

    @override_settings(**{**ZARINPAL_SETTINGS, "DEFAULT_PAYMENT_METHOD": "online"})
    def test_checkout_view_redirects_with_user_message_on_provider_error(
        self, user, product, mocker
    ):
        _mock_zarinpal_http_error(mocker)
        create_cart_with_item(user, product)

        client = Client()
        client.force_login(user)
        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": CUSTOMER["first_name"],
                "last_name": CUSTOMER["last_name"],
                "phone": CUSTOMER["phone"],
                "email": CUSTOMER["email"],
                "payment_method": Order.PaymentMethod.ONLINE,
            },
        )

        assert response.status_code == 302
        assert response.url == reverse("core:cart")
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert ONLINE_PAYMENT_UNAVAILABLE_MESSAGE in messages
        assert Order.objects.filter(user=user).count() == 0


@pytest.mark.integration
@pytest.mark.zarinpal_integration
@pytest.mark.django_db
class TestZarinpalOnlinePaymentFlow:
    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_checkout_callback_success(self, user, product, mocker):
        mock_request = mocker.Mock()
        mock_request.json.return_value = {
            "data": {"code": 100, "authority": "A000000000000000000000000000000000"},
            "errors": [],
        }
        mock_request.raise_for_status = mocker.Mock()

        mock_verify = mocker.Mock()
        mock_verify.json.return_value = {
            "data": {"code": 100, "ref_id": 55667788},
            "errors": [],
        }
        mock_verify.raise_for_status = mocker.Mock()

        mocker.patch(
            "payments.providers.zarinpal.requests.post",
            side_effect=[mock_request, mock_verify],
        )

        cart = create_cart_with_item(user, product)
        checkout = process_checkout(cart, CUSTOMER, user=user)
        order = checkout.order
        payment = checkout.payment

        assert payment.provider == Payment.Provider.ZARINPAL
        assert payment.amount == order.total
        assert payment.currency == "irr"
        assert order.delivery_fee == Decimal("0.00")

        duplicate = PaymentService.initiate_online(order)
        assert duplicate.pk == payment.pk

        payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "OK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")
        handle_zarinpal_callback(payload)

        payment.refresh_from_db()
        order.refresh_from_db()
        assert payment.status == Payment.Status.SUCCEEDED
        assert payment.provider_payment_id == "55667788"
        assert order.payment_status == Order.PaymentStatus.PAID
        assert order.status == Order.Status.CONFIRMED_BY_SHOP

    @override_settings(**ZARINPAL_SETTINGS)
    def test_zarinpal_failed_callback_then_new_checkout(self, user, product, mocker):
        mock_request = mocker.Mock()
        mock_request.json.return_value = {
            "data": {"code": 100, "authority": "A000000000000000000000000000000000"},
            "errors": [],
        }
        mock_request.raise_for_status = mocker.Mock()
        mocker.patch(
            "payments.providers.zarinpal.requests.post",
            return_value=mock_request,
        )
        mocker.patch("orders.services.order_service.StockService.release_reservations")

        cart = create_cart_with_item(user, product)
        checkout = process_checkout(cart, CUSTOMER, user=user)
        order = checkout.order
        payment = checkout.payment

        payload = json.dumps(
            {
                "authority": payment.provider_checkout_session_id,
                "status": "NOK",
                "payment_id": payment.pk,
            }
        ).encode("utf-8")
        handle_zarinpal_callback(payload)

        order.refresh_from_db()
        assert order.status == Order.Status.CANCELLED
        assert order.payment_status == Order.PaymentStatus.FAILED

        product2 = create_product(name="Retry Cookie", price=Decimal("120000"))
        cart2 = create_cart_with_item(user, product2)
        second = process_checkout(cart2, CUSTOMER, user=user)
        assert second.payment.provider == Payment.Provider.ZARINPAL
        assert second.payment.status == Payment.Status.PROCESSING
