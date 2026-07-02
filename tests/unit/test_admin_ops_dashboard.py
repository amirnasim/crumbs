from datetime import timedelta
from uuid import uuid4

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.utils import timezone

from core.admin_views import build_zarinpal_setup_status
from inventory.models import ProductInventory
from orders.models import Order
from payments.models import Payment
from products.models import Product
from tests.factories import create_order, create_product, create_user

User = get_user_model()

VALID_MERCHANT_ID = str(uuid4())
ZARINPAL_OPS_SETTINGS = {
    "DEFAULT_PAYMENT_PROVIDER": "zarinpal",
    "PAYMENT_PROVIDER": "zarinpal",
    "ZARINPAL_MERCHANT_ID": VALID_MERCHANT_ID,
    "ZARINPAL_SANDBOX": True,
    "ZARINPAL_CALLBACK_URL": "https://example.com/payments/zarinpal/callback/",
    "DEFAULT_PAYMENT_METHOD": "online",
    "ONLINE_PAYMENT_CURRENCY": "irr",
}


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="ops-staff",
        email="ops-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestOpsDashboardAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/ops/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/ops/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    @override_settings(**ZARINPAL_OPS_SETTINGS)
    def test_staff_user_can_view_dashboard(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/ops/")

        assert response.status_code == 200
        assert b"Operations Task Center" in response.content


@pytest.mark.django_db
class TestOpsDashboardContext:
    @override_settings(**ZARINPAL_OPS_SETTINGS)
    def test_context_includes_inventory_order_payment_and_zarinpal_status(
        self, client, staff_user, mocker
    ):
        zarinpal_post = mocker.patch("payments.providers.zarinpal.requests.post")

        user = create_user(username="ops-customer")
        product = create_product(stock_quantity=1)
        inventory = product.inventory
        inventory.low_stock_threshold = 5
        inventory.stock_quantity = 3
        inventory.reserved_quantity = 1
        inventory.save(update_fields=["low_stock_threshold", "stock_quantity", "reserved_quantity"])

        create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.COD_PENDING,
            payment_method=Order.PaymentMethod.COD,
        )
        create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        create_order(
            user,
            product,
            status=Order.Status.OUT_FOR_DELIVERY,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        delivered_cod = create_order(
            user,
            product,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.COD_PENDING,
            payment_method=Order.PaymentMethod.COD,
            delivery_type=Order.DeliveryType.COD,
            delivery_fee=Decimal("50000"),
        )

        stale_order = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        stale_payment = Payment.objects.create(
            order=stale_order,
            provider=Payment.Provider.ZARINPAL,
            status=Payment.Status.PENDING,
            amount=stale_order.total,
        )
        Payment.objects.filter(pk=stale_payment.pk).update(
            created_at=timezone.now() - timedelta(minutes=45),
        )
        Payment.objects.create(
            order=stale_order,
            provider=Payment.Provider.STRIPE,
            status=Payment.Status.FAILED,
            amount=stale_order.total,
            failure_message="Declined",
        )

        inconsistent_paid = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        Payment.objects.create(
            order=inconsistent_paid,
            provider=Payment.Provider.ZARINPAL,
            status=Payment.Status.PENDING,
            amount=inconsistent_paid.total,
        )

        inconsistent_cash = create_order(
            user,
            product,
            status=Order.Status.DELIVERED,
            payment_status=Order.PaymentStatus.CASH_RECEIVED,
            payment_method=Order.PaymentMethod.COD,
        )
        Payment.objects.create(
            order=inconsistent_cash,
            provider=Payment.Provider.COD,
            status=Payment.Status.PENDING,
            amount=inconsistent_cash.total,
        )

        no_inventory = create_product(name="Ghost Cookie", stock_quantity=10)
        ProductInventory.objects.filter(product=no_inventory).delete()

        client.force_login(staff_user)
        response = client.get("/admin/ops/")

        assert response.status_code == 200
        counts = response.context["counts"]
        zarinpal_status = response.context["zarinpal_status"]

        assert counts["low_stock"] == 1
        assert counts["out_of_stock"] == 0
        assert counts["products_without_inventory"] == 1
        assert counts["reserved_rows"] == 1
        assert counts["new_orders"] == 1
        assert counts["confirmed_orders"] == 2
        assert counts["preparing_orders"] == 1
        assert counts["ready_for_pickup_orders"] == 0
        assert counts["delivered_pending_finalization"] == 1
        assert counts["legacy_cod_pending_collection"] == 2
        assert counts["legacy_out_for_delivery_orders"] == 1
        assert counts["failed_payments"] == 1
        assert counts["stale_online_payments"] == 1
        assert counts["order_paid_payment_pending"] == 2
        assert counts["cash_received_payment_pending"] == 1

        assert zarinpal_status["default_payment_provider"] == "zarinpal"
        assert zarinpal_status["zarinpal_sandbox"] is True
        assert zarinpal_status["merchant_id_exists"] is True
        assert zarinpal_status["merchant_id_valid_length"] is True
        assert zarinpal_status["online_payment_enabled"] is True
        assert zarinpal_status["ready_for_sandbox_test"] is True
        assert delivered_cod.order_number.encode() in response.content

        zarinpal_post.assert_not_called()

    @override_settings(
        DEFAULT_PAYMENT_PROVIDER="zarinpal",
        ZARINPAL_MERCHANT_ID="",
        ZARINPAL_SANDBOX=True,
        ZARINPAL_CALLBACK_URL="",
        DEFAULT_PAYMENT_METHOD="cod",
    )
    def test_zarinpal_status_without_merchant_id(self):
        status = build_zarinpal_setup_status()

        assert status["merchant_id_exists"] is False
        assert status["merchant_id_valid_length"] is False
        assert status["online_payment_enabled"] is False
        assert status["ready_for_sandbox_test"] is False

    @override_settings(**ZARINPAL_OPS_SETTINGS)
    def test_no_zarinpal_api_call_on_page_load(self, client, staff_user, mocker):
        zarinpal_post = mocker.patch("payments.providers.zarinpal.requests.post")
        client.force_login(staff_user)

        response = client.get("/admin/ops/")

        assert response.status_code == 200
        zarinpal_post.assert_not_called()
