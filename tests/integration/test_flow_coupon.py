"""Flow C: Apply coupon → discount validation → order total correctness."""

from decimal import Decimal

import pytest
from django.test import override_settings

from delivery.services import process_checkout
from growth.coupon_service import CouponService
from tests.factories import CUSTOMER, create_cart_with_item
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


@pytest.mark.integration
@pytest.mark.django_db
class TestCouponFlow:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_coupon_applied_at_checkout(self, user, product, coupon, mock_stripe_checkout):
        cart = create_cart_with_item(user, product)
        cart.applied_coupon_code = coupon.code
        cart.save(update_fields=["applied_coupon_code"])

        expected = CouponService.calculate_discount(coupon, cart.get_subtotal())
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order

        assert order.discount_amount == expected
        assert order.delivery_fee == Decimal("0.00")
        assert order.total == order.subtotal - expected
