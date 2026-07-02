"""Unit tests for CouponService."""

from decimal import Decimal

import pytest

from growth.coupon_service import CouponService
from growth.models import Coupon
from orders.models import Order
from tests.factories import create_coupon, create_order, create_product, create_user


@pytest.mark.django_db
class TestCouponService:
    def test_percentage_discount_calculation(self, coupon):
        amount = CouponService.calculate_discount(coupon, Decimal("200000"))
        assert amount == Decimal("20000.00")

    def test_fixed_discount_capped_at_subtotal(self):
        coupon = create_coupon(
            code="FIXED50K",
            discount_type=Coupon.DiscountType.FIXED,
            discount_value=50000,
        )
        amount = CouponService.calculate_discount(coupon, Decimal("30000"))
        assert amount == Decimal("30000")

    def test_validate_rejects_expired_code(self):
        coupon = create_coupon(code="DEAD")
        coupon.is_active = False
        coupon.save(update_fields=["is_active"])
        result = CouponService.validate("DEAD", subtotal=Decimal("100000"))
        assert result.coupon is None
        assert result.error

    def test_first_order_coupon_rejects_repeat_buyer(self, first_order_coupon):
        user = create_user()
        product = create_product()
        create_order(user, product, payment_status=Order.PaymentStatus.PAID, status=Order.Status.PAID)
        result = CouponService.validate(
            first_order_coupon.code,
            subtotal=Decimal("100000"),
            user=user,
        )
        assert result.coupon is None
        assert "first order" in result.error.lower()

    def test_usage_limit_per_user(self, coupon):
        from growth.models import CouponRedemption

        user = create_user()
        product = create_product()
        order = create_order(user, product)
        order.discount_amount = Decimal("15000")
        order.save(update_fields=["discount_amount"])
        CouponRedemption.objects.create(
            coupon=coupon,
            user=user,
            order=order,
            discount_amount=order.discount_amount,
        )
        result = CouponService.validate(coupon.code, subtotal=Decimal("200000"), user=user)
        assert result.coupon is None
        assert "limit" in result.error.lower()

    def test_redeem_increments_usage_count(self, coupon):
        user = create_user()
        product = create_product()
        order = create_order(user, product)
        order.discount_amount = Decimal("15000")
        order.save(update_fields=["discount_amount"])
        CouponService.redeem(coupon, order, user=user)
        coupon.refresh_from_db()
        assert coupon.usage_count == 1

    def test_global_usage_cap(self):
        coupon = create_coupon(code="GLOBAL1", usage_limit_global=1, usage_limit_per_user=5)
        user_a = create_user(username="a", email="a@test.com")
        user_b = create_user(username="b", email="b@test.com")
        product = create_product()
        coupon.usage_count = 1
        coupon.save(update_fields=["usage_count"])
        result = CouponService.validate(coupon.code, subtotal=Decimal("100000"), user=user_b)
        assert result.coupon is None
