"""Persian-first Django admin configuration tests."""

from unittest.mock import Mock

import pytest
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.contrib.sessions.middleware import SessionMiddleware
from django.http import HttpResponse
from django.test import Client, RequestFactory
from django.urls import reverse

from careers.admin import CareerApplicationAdmin
from careers.models import CareerApplication
from core.admin_branding import configure_admin_site
from inventory.admin import ProductInventoryAdmin, StockReservationAdmin
from inventory.models import ProductInventory, StockReservation
from orders.admin import OrderAdmin
from orders.models import Order
from orders.services.order_service import OrderService
from payments.admin import PaymentAdmin
from payments.models import Payment
from products.admin import ProductAdmin
from products.models import Product
from tests.factories import create_order, create_product, create_user

User = get_user_model()


@pytest.fixture
def admin_request(rf):
    request = rf.get("/admin/")
    request.user = Mock(is_active=True, is_staff=True, is_superuser=True)
    return request


@pytest.fixture(autouse=True)
def _admin_branding():
    configure_admin_site()


@pytest.mark.django_db
class TestAdminSiteBranding:
    def test_persian_site_headers(self):
        assert admin.site.site_header == "مدیریت Crumbs"
        assert admin.site.site_title == "پنل مدیریت Crumbs"
        assert admin.site.index_title == "داشبورد مدیریت"

    def test_language_code_is_persian(self):
        assert settings.LANGUAGE_CODE == "fa"
        assert settings.TIME_ZONE == "Asia/Tehran"
        assert settings.USE_I18N is True
        assert settings.USE_TZ is True


@pytest.mark.django_db
class TestAdminRtlLocalization:
    def test_admin_login_page_is_rtl_persian(self, client):
        response = client.get(reverse("admin:login"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'lang="fa"' in content
        assert 'dir="rtl"' in content
        assert "ورود" in content

    def test_admin_index_is_rtl_for_staff(self, client, staff_user):
        client.force_login(staff_user)
        response = client.get(reverse("admin:index"))
        content = response.content.decode()

        assert response.status_code == 200
        assert 'dir="rtl"' in content
        assert "سفارش‌ها" in content or "محصولات" in content


@pytest.mark.django_db
class TestModelPersianVerboseNames:
    def test_key_models_have_persian_plural_names(self):
        assert Order._meta.verbose_name_plural == "سفارش‌ها"
        assert Payment._meta.verbose_name_plural == "پرداخت‌ها"
        assert Product._meta.verbose_name_plural == "محصولات"
        assert CareerApplication._meta.verbose_name_plural == "درخواست‌های همکاری"
        assert ProductInventory._meta.verbose_name_plural == "موجودی محصولات"


@pytest.fixture
def staff_user(db):
    return User.objects.create_user(
        username="rtl-admin",
        email="rtl-admin@example.com",
        password="pass12345",
        is_staff=True,
        is_superuser=True,
    )


@pytest.fixture
def client():
    return Client()


class TestOrderAdminConfiguration:
    def test_list_display_has_operational_columns(self):
        order_admin = OrderAdmin(Order, admin.site)
        assert "order_number" in order_admin.list_display
        assert "customer_name" in order_admin.list_display
        assert "phone" in order_admin.list_display
        assert "status_fa" in order_admin.list_display
        assert "payment_method_fa" in order_admin.list_display
        assert "total" in order_admin.list_display
        assert "created_at" in order_admin.list_display

    def test_filters_and_search(self):
        order_admin = OrderAdmin(Order, admin.site)
        assert "status" in order_admin.list_filter
        assert "payment_method" in order_admin.list_filter
        assert "delivery_type" in order_admin.list_filter
        assert "created_at" in order_admin.list_filter
        assert "order_number" in order_admin.search_fields
        assert "phone" in order_admin.search_fields
        assert "email" in order_admin.search_fields

    def test_readonly_totals_and_identifiers(self):
        order_admin = OrderAdmin(Order, admin.site)
        readonly = set(order_admin.readonly_fields)
        assert {"order_number", "total", "payment_status", "created_at", "updated_at"} <= readonly

    def test_lifecycle_action_descriptions_are_persian(self, admin_request):
        order_admin = OrderAdmin(Order, admin.site)
        actions = order_admin.get_actions(admin_request)
        assert actions["advance_to_preparing"][2] == "علامت‌گذاری به عنوان در حال آماده‌سازی"
        assert actions["advance_to_packaged"][2] == "علامت‌گذاری به عنوان آماده تحویل"
        assert actions["mark_delivered"][2] == "علامت‌گذاری به عنوان تحویل‌شده"
        assert actions["cancel_orders"][2] == "لغو سفارش"

    def test_bulk_delete_removed(self, admin_request):
        order_admin = OrderAdmin(Order, admin.site)
        assert "delete_selected" not in order_admin.get_actions(admin_request)


@pytest.mark.django_db
class TestOrderAdminActionsSafety:
    def test_cancel_action_uses_order_service(self, mocker):
        user = create_user(username="cancel-admin-user")
        product = create_product()
        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.PAID,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        spy = mocker.spy(OrderService, "cancel")
        order_admin = OrderAdmin(Order, admin.site)

        from django.contrib.messages.storage.fallback import FallbackStorage
        from django.contrib.sessions.middleware import SessionMiddleware
        from django.http import HttpResponse
        from django.test import RequestFactory

        rf = RequestFactory()
        staff = User.objects.create_user(
            username="staff-cancel",
            email="staff@example.com",
            password="pass",
            is_staff=True,
            is_superuser=True,
        )
        request = rf.post("/admin/orders/order/")
        request.user = staff
        middleware = SessionMiddleware(lambda req: HttpResponse())
        middleware.process_request(request)
        request.session.save()
        request._messages = FallbackStorage(request)

        order_admin.cancel_orders(request, Order.objects.filter(pk=order.pk))

        spy.assert_called_once()


class TestPaymentAdminConfiguration:
    def test_list_display_and_filters(self):
        payment_admin = PaymentAdmin(Payment, admin.site)
        assert "order_link" in payment_admin.list_display
        assert "provider_fa" in payment_admin.list_display
        assert "status_fa" in payment_admin.list_display
        assert "provider" in payment_admin.list_filter
        assert "status" in payment_admin.list_filter
        assert "created_at" in payment_admin.list_filter
        assert "order__order_number" in payment_admin.search_fields

    def test_bulk_delete_removed(self, admin_request):
        payment_admin = PaymentAdmin(Payment, admin.site)
        assert "delete_selected" not in payment_admin.get_actions(admin_request)

    def test_metadata_not_exposed_raw(self):
        payment_admin = PaymentAdmin(Payment, admin.site)
        assert "metadata" not in payment_admin.readonly_fields
        assert "metadata_safe" in payment_admin.readonly_fields


class TestProductAdminConfiguration:
    def test_list_display_and_fieldsets(self):
        product_admin = ProductAdmin(Product, admin.site)
        assert "thumbnail_preview" in product_admin.list_display
        assert "availability_fa" in product_admin.list_display
        assert "stock_summary" in product_admin.list_display
        fieldset_titles = [fs[0] for fs in product_admin.fieldsets]
        assert "اطلاعات اصلی" in fieldset_titles
        assert "قیمت و فروش" in fieldset_titles
        assert "تصویر و رسانه" in fieldset_titles


class TestInventoryAdminConfiguration:
    def test_inventory_list_display(self):
        inv_admin = ProductInventoryAdmin(ProductInventory, admin.site)
        assert "stock_quantity" in inv_admin.list_display
        assert "reserved_quantity" in inv_admin.list_display
        assert "available_display" in inv_admin.list_display
        assert "updated_at" in inv_admin.list_display

    def test_stock_reservation_bulk_delete_removed(self, admin_request):
        res_admin = StockReservationAdmin(StockReservation, admin.site)
        assert "delete_selected" not in res_admin.get_actions(admin_request)


class TestCareerAdminConfiguration:
    def test_list_includes_email_and_persian_actions(self, admin_request):
        career_admin = CareerApplicationAdmin(CareerApplication, admin.site)
        assert "email" in career_admin.list_display
        assert "status_fa" in career_admin.list_display
        actions = career_admin.get_actions(admin_request)
        assert actions["mark_reviewing"][2] == "علامت‌گذاری به عنوان در حال بررسی"
        assert actions["mark_hired"][2] == "علامت‌گذاری به عنوان پذیرفته‌شده"
        assert actions["mark_rejected"][2] == "علامت‌گذاری به عنوان رد شده"

    def test_delete_disabled(self, admin_request):
        career_admin = CareerApplicationAdmin(CareerApplication, admin.site)
        assert career_admin.has_delete_permission(admin_request) is False
        assert "delete_selected" not in career_admin.get_actions(admin_request)
