"""Coupon validation, discount calculation, and redemption auditing."""

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import F

from growth.models import Coupon, CouponRedemption
from orders.models import Order


class CouponError(Exception):
    pass


@dataclass
class CouponResult:
    coupon: Coupon | None
    discount_amount: Decimal
    error: str = ""


class CouponService:
    PAID_STATUSES = {Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED}

    @staticmethod
    def normalize_code(code: str) -> str:
        return code.strip().upper()

    @classmethod
    def get_active(cls, code: str) -> Coupon | None:
        normalized = cls.normalize_code(code)
        try:
            coupon = Coupon.objects.get(code__iexact=normalized)
        except Coupon.DoesNotExist:
            return None
        return coupon if coupon.is_valid_now else None

    @classmethod
    def calculate_discount(cls, coupon: Coupon, subtotal: Decimal) -> Decimal:
        if coupon.discount_type == Coupon.DiscountType.PERCENTAGE:
            amount = (subtotal * coupon.discount_value / Decimal("100")).quantize(Decimal("0.01"))
        else:
            amount = min(coupon.discount_value, subtotal)

        if coupon.max_discount_amount is not None:
            amount = min(amount, coupon.max_discount_amount)
        return max(Decimal("0.00"), amount)

    @classmethod
    def validate(cls, code: str, *, subtotal: Decimal, user=None) -> CouponResult:
        if not code:
            return CouponResult(coupon=None, discount_amount=Decimal("0.00"))

        coupon = cls.get_active(code)
        if coupon is None:
            return CouponResult(coupon=None, discount_amount=Decimal("0.00"), error="Invalid or expired coupon.")

        if subtotal < coupon.min_order_amount:
            return CouponResult(
                coupon=None,
                discount_amount=Decimal("0.00"),
                error=f"Minimum order amount is {int(coupon.min_order_amount)}.",
            )

        if coupon.campaign_type == Coupon.CampaignType.FIRST_ORDER and user:
            if Order.objects.filter(user=user, payment_status__in=cls.PAID_STATUSES).exists():
                return CouponResult(
                    coupon=None,
                    discount_amount=Decimal("0.00"),
                    error="This coupon is for first orders only.",
                )

        if user:
            user_uses = CouponRedemption.objects.filter(coupon=coupon, user=user).count()
            if user_uses >= coupon.usage_limit_per_user:
                return CouponResult(
                    coupon=None,
                    discount_amount=Decimal("0.00"),
                    error="Coupon usage limit reached for this account.",
                )

        discount = cls.calculate_discount(coupon, subtotal)
        return CouponResult(coupon=coupon, discount_amount=discount)

    @classmethod
    @transaction.atomic
    def redeem(cls, coupon: Coupon, order: Order, *, user=None) -> CouponRedemption:
        redemption, created = CouponRedemption.objects.get_or_create(
            order=order,
            defaults={
                "coupon": coupon,
                "user": user or order.user,
                "discount_amount": order.discount_amount,
            },
        )
        if created:
            Coupon.objects.filter(pk=coupon.pk).update(usage_count=F("usage_count") + 1)
        return redemption
