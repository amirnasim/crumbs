from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.models import BackgroundTaskLog
from inventory.models import ProductInventory
from orders.models import Order
from payments.models import Payment
from products.models import Product
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


@pytest.mark.django_db
class TestOperationsDashboardAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/operations/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/operations/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_staff_user_can_view_dashboard(self, client, staff_user):
        client.force_login(staff_user)

        response = client.get("/admin/operations/")

        assert response.status_code == 200
        assert b"Operations Dashboard" in response.content


@pytest.mark.django_db
class TestOperationsDashboardContext:
    def test_context_counts_reflect_operational_data(self, client, staff_user):
        user = create_user(username="customer")
        product = create_product(stock_quantity=1)
        inventory = product.inventory
        inventory.low_stock_threshold = 5
        inventory.reserved_quantity = 0
        inventory.stock_quantity = 3
        inventory.save(update_fields=["low_stock_threshold", "reserved_quantity", "stock_quantity"])

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
            delivery_type=Order.DeliveryType.COD,
            delivery_fee=Decimal("50000"),
        )
        create_order(
            user,
            product,
            status=Order.Status.PREPARING,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
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
            provider=Payment.Provider.STRIPE,
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
            failure_message="Card declined",
        )

        BackgroundTaskLog.objects.create(
            task_name="notifications.send_sms",
            task_id="task-failure-1",
            status=BackgroundTaskLog.Status.FAILURE,
            error_message="Provider timeout",
        )

        inactive = create_product(name="Stale Cookie", stock_quantity=10)
        inactive.availability_status = Product.AvailabilityStatus.OUT_OF_STOCK
        inactive.save(update_fields=["availability_status"])

        no_inventory = create_product(name="Ghost Cookie", stock_quantity=10)
        ProductInventory.objects.filter(product=no_inventory).delete()

        bad_price = create_product(name="Free Cookie", price=Decimal("0"))

        client.force_login(staff_user)
        response = client.get("/admin/operations/")

        assert response.status_code == 200
        counts = response.context["counts"]
        assert counts["new_orders"] == 2
        assert counts["legacy_cod_to_collect"] == 1
        assert counts["orders_in_preparation"] == 2
        assert counts["low_stock"] == 1
        assert counts["failed_tasks"] == 1
        assert counts["payment_issues"] == 2
        assert counts["inactive_products"] == 1
        assert counts["products_without_inventory"] == 1
        assert counts["invalid_price_products"] == 1
        assert counts["products_missing_category"] == 0

    def test_order_admin_links_use_reverse(self, client, staff_user):
        user = create_user(username="link-user")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.PENDING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )

        client.force_login(staff_user)
        response = client.get("/admin/operations/")

        expected_url = reverse("admin:orders_order_change", args=[order.pk])
        assert expected_url.encode() in response.content
