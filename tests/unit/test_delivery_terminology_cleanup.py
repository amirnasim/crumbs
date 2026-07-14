"""Delivery terminology cleanup — in-cafe pickup wording in active UI/admin."""

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from orders.models import Order
from tests.factories import create_cart_with_item, create_order, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS

User = get_user_model()

FORBIDDEN_CHECKOUT_TERMS = (
    "delivery",
    "courier",
    "shipping",
    "پیک",
    "ارسال",
    "روش ارسال",
    "آدرس تحویل",
    "هزینه ارسال",
    "کد پستی",
    "delivery fee",
    "delivery zone",
)

FORBIDDEN_INCAFE_ORDER_TERMS = (
    "delivery",
    "courier",
    "shipping",
    "روش ارسال",
    "آدرس تحویل",
    "هزینه ارسال",
    "delivery fee",
    "delivery zone",
)

FORBIDDEN_ACTIVE_ADMIN_TERMS = (
    "Out For Delivery",
    "delivery pipeline",
    "cash-on-delivery",
    "courier",
)


@pytest.fixture
def client():
    return Client()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="cleanup-staff",
        email="cleanup-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.mark.django_db
class TestCheckoutDeliveryWordingRemoved:
    def test_checkout_page_has_no_delivery_address_wording(self, client, user, product):
        create_cart_with_item(user, product)
        client.force_login(user)

        response = client.get(reverse("core:checkout"))

        content = response.content.decode()
        assert response.status_code == 200
        assert "سفارش حضوری" in content
        assert "پرداخت آنلاین" in content
        assert "پرداخت حضوری" in content
        assert "پرداخت هنگام تحویل سفارش (نقدی یا کارت)" in content
        assert "پرداخت با کارت در صندوق" not in content
        assert "پرداخت نقدی در صندوق" not in content
        for term in FORBIDDEN_CHECKOUT_TERMS:
            assert term not in content
        assert "شهر" not in content


@pytest.mark.django_db
class TestInCafeOrderSummaryWording:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_order_detail_hides_delivery_blocks_for_pickup_order(
        self, client, user, product, mock_stripe_checkout
    ):
        order = create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            delivery_type=Order.DeliveryType.PICKUP,
        )
        order.notes = "Table 3"
        order.save(update_fields=["notes", "updated_at"])
        client.force_login(user)

        response = client.get(reverse("accounts:order_detail", args=[order.order_number]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "نوع دریافت" in content
        assert "تحویل از کانتر" in content
        assert "میز / یادداشت" in content
        assert "Table 3" in content
        for term in FORBIDDEN_INCAFE_ORDER_TERMS:
            assert term not in content

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_confirmation_page_hides_delivery_blocks_for_pickup_order(
        self, client, user, product, mock_stripe_checkout
    ):
        order = create_order(
            user,
            product,
            status=Order.Status.PACKAGED,
            payment_status=Order.PaymentStatus.PAID,
            delivery_type=Order.DeliveryType.PICKUP,
        )
        session = client.session
        session["checkout_order_access"] = [order.order_number]
        session.save()

        response = client.get(reverse("core:order_confirmation", args=[order.order_number]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "آماده تحویل از کانتر" in content
        for term in FORBIDDEN_INCAFE_ORDER_TERMS:
            assert term not in content


@pytest.mark.django_db
class TestActiveAdminDeliveryWordingRemoved:
    def test_ops_dashboard_has_no_active_delivery_wording(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/ops/")

        content = response.content.decode()
        assert response.status_code == 200
        for term in FORBIDDEN_ACTIVE_ADMIN_TERMS:
            assert term not in content
        assert "Ready For Pickup — آماده تحویل" in content

    def test_kitchen_queue_uses_pickup_wording(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/kitchen/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Kitchen Queue" in content
        assert "سفارش حضوری" in content
        assert "آماده تحویل" in content
        assert "تحویل شد" in content
        for term in FORBIDDEN_ACTIVE_ADMIN_TERMS:
            assert term not in content

    def test_pickup_screen_uses_pickup_wording(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/pickup-screen/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Pickup Screen" in content
        assert "آماده تحویل" in content
        assert "تحویل شد" in content
        for term in FORBIDDEN_ACTIVE_ADMIN_TERMS:
            assert term not in content

    def test_operations_dashboard_has_no_delivery_pipeline_wording(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/operations/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "delivery pipeline" not in content.lower()
        assert "cash-on-delivery" not in content.lower()
