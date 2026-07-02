"""Safe delivery field deprecation — in-cafe defaults without column removal."""

from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from django.test import Client, override_settings
from django.urls import reverse

from cart.services import add_item, get_or_create_cart
from orders.models import Order
from orders.services import create_order_from_cart
from tests.factories import create_delivery_zone, create_order, create_product, create_user
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS

User = get_user_model()


@pytest.mark.django_db
class TestInCafeOrdersWithoutDeliveryFields:
    def test_create_order_from_cart_defaults_to_pickup_without_address(self, user, product):
        cart, _ = get_or_create_cart(user=user)
        add_item(cart, product, 1)

        order = create_order_from_cart(
            cart,
            {
                "email": user.email,
                "first_name": "Sara",
                "last_name": "Karimi",
                "phone": "09121234567",
                "address_line1": "Should be ignored",
                "city": "Tehran",
                "postal_code": "1234567890",
                "delivery_type": Order.FulfillmentType.PICKUP,
            },
        )

        assert order.fulfillment_type == Order.FulfillmentType.PICKUP
        assert order.delivery_type == Order.FulfillmentType.PICKUP
        assert order.address_line1 == ""
        assert order.address_line2 == ""
        assert order.city == ""
        assert order.state == ""
        assert order.postal_code == ""
        assert order.delivery_zone_id is None
        assert order.delivery_fee == Decimal("0.00")

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_online_checkout_still_works_without_delivery_fields(
        self, client, user, product, mock_stripe_checkout
    ):
        cart, _ = get_or_create_cart(user=user)
        add_item(cart, product, 1)
        client.force_login(user)

        response = client.post(
            reverse("core:checkout"),
            data={
                "first_name": "Sara",
                "phone": "09121234567",
                "email": "",
                "pickup_note": "Table 4",
                "payment_method": Order.PaymentMethod.ONLINE,
            },
        )

        assert response.status_code == 200
        order = Order.objects.get(user=user)
        assert order.delivery_type == Order.FulfillmentType.PICKUP
        assert order.address_line1 == ""
        assert order.delivery_zone_id is None


@pytest.mark.django_db
class TestLegacyDeliveryOrdersPreserved:
    def test_legacy_cod_order_retains_delivery_fields(self, user, product):
        zone = create_delivery_zone()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.COD,
            delivery_type=Order.FulfillmentType.COD,
            delivery_fee=Decimal("50000"),
            delivery_zone=zone,
        )
        order.address_line1 = "Legacy Valiasr 42"
        order.city = "Tehran"
        order.postal_code = "1234567890"
        order.save(
            update_fields=[
                "address_line1",
                "city",
                "postal_code",
                "updated_at",
            ]
        )

        order.refresh_from_db()

        assert order.has_legacy_delivery_details
        assert order.address_line1 == "Legacy Valiasr 42"
        assert order.delivery_zone_id == zone.pk
        assert order.delivery_fee == Decimal("50000")

    def test_staff_can_view_legacy_order_in_admin(self, client, product):
        staff = User.objects.create_superuser(
            username="legacy-admin",
            email="legacy-admin@example.com",
            password="pass12345",
        )
        user = create_user(username="legacy-customer")
        zone = create_delivery_zone()
        order = create_order(
            user,
            product,
            payment_method=Order.PaymentMethod.COD,
            delivery_type=Order.FulfillmentType.COD,
            delivery_fee=Decimal("50000"),
            delivery_zone=zone,
        )
        order.address_line1 = "Legacy Admin Street"
        order.save(update_fields=["address_line1", "updated_at"])

        client.force_login(staff)
        response = client.get(reverse("admin:orders_order_change", args=[order.pk]))

        content = response.content.decode()
        assert response.status_code == 200
        assert "دریافت / تحویل (قدیمی)" in content
        assert "Legacy Admin Street" in content
        assert order.get_fulfillment_type_display() == "COD (legacy)"

    def test_pickup_order_model_default_is_pickup(self):
        field = Order._meta.get_field("delivery_type")
        assert field.default == Order.FulfillmentType.PICKUP

    def test_address_fields_allow_blank(self):
        for field_name in ("address_line1", "city", "postal_code", "state", "address_line2"):
            field = Order._meta.get_field(field_name)
            assert field.blank is True
