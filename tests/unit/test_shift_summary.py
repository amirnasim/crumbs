"""Staff daily shift summary page."""

from datetime import date, datetime, time
from decimal import Decimal
from pathlib import Path

import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from core.shift_summary import build_shift_summary, parse_shift_date
from inventory.models import ProductInventory
from orders.models import Order, OrderItem
from payments.models import Payment
from tests.factories import create_order, create_product, create_user

User = get_user_model()
ORDERS_MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "apps" / "orders" / "migrations"


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="shift-staff",
        email="shift-staff@example.com",
        password="pass12345",
        is_staff=True,
    )


@pytest.fixture
def client():
    return Client()


def _shift_url(**params):
    url = reverse("admin:crumbs_shift_summary")
    if not params:
        return url
    query = "&".join(f"{key}={value}" for key, value in params.items())
    return f"{url}?{query}"


def _set_order_created_at(order, day: date, *, hour: int = 12):
    tz = timezone.get_current_timezone()
    created_at = timezone.make_aware(datetime.combine(day, time(hour=hour)), tz)
    Order.objects.filter(pk=order.pk).update(created_at=created_at, updated_at=created_at)
    order.refresh_from_db()


@pytest.mark.django_db
class TestShiftSummaryAccess:
    def test_anonymous_user_redirected_to_admin_login(self, client):
        response = client.get("/admin/shift-summary/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_non_staff_user_redirected_to_admin_login(self, client, db):
        user = User.objects.create_user(username="buyer", password="pass12345")
        client.force_login(user)

        response = client.get("/admin/shift-summary/")

        assert response.status_code == 302
        assert "/admin/login/" in response.url

    def test_staff_user_can_view_today_summary(self, client, staff_user, product):
        user = create_user(username="shift-guest")
        order = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        _set_order_created_at(order, timezone.localdate())

        client.force_login(staff_user)
        response = client.get("/admin/shift-summary/")

        content = response.content.decode()
        assert response.status_code == 200
        assert "Shift Summary" in content
        assert order.order_number in content
        assert response.context["summary"].paid_order_count >= 1


@pytest.mark.django_db
class TestShiftSummaryMetrics:
    def test_date_filter_limits_orders_to_selected_day(self, product):
        user = create_user(username="shift-date-user")
        target_day = date(2026, 6, 5)
        other_day = date(2026, 6, 4)

        included = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.CASH,
        )
        excluded = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        _set_order_created_at(included, target_day)
        _set_order_created_at(excluded, other_day)

        summary = build_shift_summary(target_day)

        assert summary.order_count == 1
        assert summary.paid_order_count == 1
        assert summary.total_sales == included.total

    def test_payment_breakdown_groups_paid_orders_by_method(self, product):
        user = create_user(username="shift-breakdown-user")
        day = date(2026, 6, 6)

        online = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        cash = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.CASH_RECEIVED,
            payment_method=Order.PaymentMethod.CASH,
        )
        card = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.COUNTER_CARD,
        )
        for order in (online, cash, card):
            _set_order_created_at(order, day)

        summary = build_shift_summary(day)
        breakdown = {row.method: row for row in summary.payment_breakdown}

        assert breakdown[Order.PaymentMethod.ONLINE].count == 1
        assert breakdown[Order.PaymentMethod.CASH].count == 1
        assert breakdown[Order.PaymentMethod.COUNTER_CARD].count == 1
        assert summary.total_sales == online.total + cash.total + card.total

    def test_top_products_ranked_by_quantity_sold(self, product):
        user = create_user(username="shift-top-user")
        day = date(2026, 6, 7)
        product_b = create_product(name="Brownie")

        order = create_order(
            user,
            product,
            status=Order.Status.PAID,
            payment_status=Order.PaymentStatus.PAID,
        )
        _set_order_created_at(order, day)
        OrderItem.objects.create(
            order=order,
            product=product_b,
            product_name=product_b.name,
            unit_price=product_b.price,
            quantity=5,
            line_total=product_b.price * 5,
        )

        summary = build_shift_summary(day)

        assert len(summary.top_products) >= 2
        assert summary.top_products[0].quantity_sold >= summary.top_products[1].quantity_sold
        names = {row.product_name for row in summary.top_products}
        assert product.name in names
        assert product_b.name in names

    def test_low_stock_products_included(self, product):
        inventory = ProductInventory.objects.get(product=product)
        inventory.stock_quantity = 1
        inventory.reserved_quantity = 0
        inventory.low_stock_threshold = 5
        inventory.save(update_fields=["stock_quantity", "reserved_quantity", "low_stock_threshold", "updated_at"])

        summary = build_shift_summary(timezone.localdate())

        assert any(row.product_id == product.pk for row in summary.low_stock)

    def test_staff_page_date_filter_query_param(self, client, staff_user, product):
        user = create_user(username="shift-query-user")
        day = date(2026, 6, 8)
        order = create_order(
            user,
            product,
            status=Order.Status.AWAITING_PAYMENT,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.CASH,
        )
        _set_order_created_at(order, day)

        client.force_login(staff_user)
        response = client.get(_shift_url(date=day.isoformat()))

        assert response.status_code == 200
        assert response.context["summary"].awaiting_counter_payment_count == 1
        assert str(day) in response.content.decode()


def test_parse_shift_date_defaults_to_today():
    assert parse_shift_date(None) == timezone.localdate()
    assert parse_shift_date("2026-06-01") == date(2026, 6, 1)


def test_no_new_migrations_created_for_shift_summary():
    migration_files = sorted(p.name for p in ORDERS_MIGRATIONS_DIR.glob("0*.py"))
    assert migration_files
    assert migration_files[-1] == "0008_persian_verbose_names.py"
