"""In-cafe checkout UI — online and counter payment options."""

import pytest
from django.contrib.messages import get_messages
from django.test import Client, override_settings
from django.urls import reverse

from cart.models import Cart
from inventory.models import StockReservation
from orders.models import Order
from payments.models import Payment
from tests.factories import create_cart_with_item, create_product, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS

CAFE_CHECKOUT_DATA = {
    "first_name": "Sara",
    "last_name": "Sara",
    "phone": "09121234567",
    "email": "",
    "pickup_note": "میز ۵",
    "payment_method": Order.PaymentMethod.CASH,
}


def _post_checkout(client, user, product, *, payment_method, pickup_note="میز ۵"):
    create_cart_with_item(user, product)
    data = {
        **CAFE_CHECKOUT_DATA,
        "pickup_note": pickup_note,
        "payment_method": payment_method,
    }
    return client.post(reverse("core:checkout"), data=data)


@pytest.fixture
def client():
    return Client()


@pytest.mark.integration
@pytest.mark.django_db
class TestCafeCheckoutUI:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_cash_checkout_creates_awaiting_payment_order(self, client, user, product, mock_stripe_checkout):
        client.force_login(user)
        response = _post_checkout(client, user, product, payment_method=Order.PaymentMethod.CASH)

        assert response.status_code == 302
        order = Order.objects.get(user=user)
        assert order.status == Order.Status.AWAITING_PAYMENT
        assert order.payment_method == Order.PaymentMethod.CASH
        assert order.notes == "میز ۵"
        assert order.delivery_fee == 0
        assert not order.address_line1
        assert order.payments.filter(provider=Payment.Provider.CASH, status=Payment.Status.PENDING).exists()
        assert StockReservation.objects.filter(
            order=order,
            status=StockReservation.Status.ACTIVE,
        ).exists()
        assert Cart.objects.get(user=user).items.count() == 0

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_counter_card_is_not_a_public_checkout_choice(
        self, client, user, product, mock_stripe_checkout
    ):
        client.force_login(user)
        response = _post_checkout(client, user, product, payment_method=Order.PaymentMethod.COUNTER_CARD)

        assert response.status_code == 200
        assert not Order.objects.filter(user=user).exists()
        content = response.content.decode()
        assert "پرداخت حضوری" in content
        assert "پرداخت با کارت در صندوق" not in content

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_online_checkout_uses_gateway_flow(self, client, user, product, mock_stripe_checkout):
        client.force_login(user)
        response = _post_checkout(client, user, product, payment_method=Order.PaymentMethod.ONLINE)

        assert response.status_code == 200
        assert response.context["checkout_url"]
        order = Order.objects.get(user=user)
        assert order.status == Order.Status.PENDING_PAYMENT
        assert order.payment_method == Order.PaymentMethod.ONLINE
        assert order.payments.filter(provider=Payment.Provider.STRIPE).exists()

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_checkout_does_not_require_delivery_fields(self, client, user, product, mock_stripe_checkout):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": "Ali",
                "phone": "09120001122",
                "pickup_note": "",
                "payment_method": Order.PaymentMethod.CASH,
            },
        )

        assert response.status_code == 302
        order = Order.objects.get(user=user)
        assert order.city == ""
        assert order.postal_code == ""

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_guest_counter_checkout_shows_confirmation_page(self, client, product, mock_stripe_checkout):
        from cart.services import add_item, get_or_create_cart

        if not client.session.session_key:
            client.session.create()
        cart, _ = get_or_create_cart(session_key=client.session.session_key)
        add_item(cart, product, 1)

        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": "Guest",
                "phone": "09123334455",
                "payment_method": Order.PaymentMethod.CASH,
            },
        )

        order = Order.objects.latest("created_at")
        assert response.status_code == 302
        assert response.url == reverse("core:order_confirmation", args=[order.order_number])

        confirm = client.get(response.url)
        assert confirm.status_code == 200
        content = confirm.content.decode()
        assert order.order_number in content
        assert "لطفاً برای پرداخت به صندوق مراجعه کنید" in content
        assert "لطفاً برای نهایی شدن سفارش به صندوق مراجعه کنید" in content
        assert "در انتظار پرداخت در صندوق" in content

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_logged_in_counter_checkout_shows_success_message(
        self, client, user, product, mock_stripe_checkout
    ):
        client.force_login(user)
        response = _post_checkout(client, user, product, payment_method=Order.PaymentMethod.CASH)

        order = Order.objects.get(user=user)
        assert response.url == reverse("accounts:order_detail", args=[order.order_number])
        messages = [str(message) for message in get_messages(response.wsgi_request)]
        assert any("لطفاً برای پرداخت به صندوق مراجعه کنید" in message for message in messages)

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_order_detail_shows_counter_payment_instructions(
        self, client, user, product, mock_stripe_checkout
    ):
        client.force_login(user)
        _post_checkout(client, user, product, payment_method=Order.PaymentMethod.CASH)
        order = Order.objects.get(user=user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        assert response.status_code == 200
        content = response.content.decode()
        assert "لطفاً برای نهایی شدن سفارش به صندوق مراجعه کنید" in content
        assert "در انتظار پرداخت در صندوق" in content

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_awaiting_counter_order_appears_in_ops_dashboard(self, client, user, product, mock_stripe_checkout):
        from django.contrib.auth import get_user_model

        staff = get_user_model().objects.create_user(
            username="cafe-staff",
            email="cafe-staff@example.com",
            password="pass12345",
            is_staff=True,
        )
        client.force_login(user)
        _post_checkout(client, user, product, payment_method=Order.PaymentMethod.CASH)

        client.force_login(staff)
        response = client.get("/admin/ops/")

        assert response.status_code == 200
        assert response.context["counts"]["awaiting_counter_payment"] >= 1
