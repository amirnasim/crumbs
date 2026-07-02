"""Checkout integration facade — applies growth pricing without touching OrderService."""

from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction

from growth.coupon_service import CouponError, CouponService
from growth.promotion_service import PromotionRuleService
from growth.referral_service import ReferralService
from orders.models import Order


@dataclass
class GrowthCheckoutContext:
    coupon_code: str = ""
    referral_code: str = ""
    coupon_discount: Decimal = Decimal("0.00")
    promotion_discount: Decimal = Decimal("0.00")
    total_discount: Decimal = Decimal("0.00")
    coupon: object | None = None
    referral_code_obj: object | None = None
    pending_referral: object | None = None
    promotion_labels: list[str] = field(default_factory=list)
    error: str = ""


class GrowthCheckoutFacade:
    @classmethod
    def prepare(cls, cart, user, customer: dict, subtotal: Decimal) -> GrowthCheckoutContext:
        ctx = GrowthCheckoutContext()
        coupon_code = (
            customer.get("coupon_code")
            or cart.applied_coupon_code
            or ""
        ).strip()
        referral_code = (
            customer.get("referral_code")
            or cart.referral_code
            or ""
        ).strip()

        ctx.coupon_code = coupon_code
        ctx.referral_code = referral_code

        if coupon_code:
            result = CouponService.validate(coupon_code, subtotal=subtotal, user=user)
            if result.error:
                ctx.error = result.error
            else:
                ctx.coupon = result.coupon
                ctx.coupon_discount = result.discount_amount

        promo = PromotionRuleService.evaluate(cart, user=user, subtotal=subtotal)
        ctx.promotion_discount = promo.total_discount
        ctx.promotion_labels = [r["name"] for r in promo.applied_rules]

        if referral_code and user:
            ctx.referral_code_obj = ReferralService.validate_for_checkout(referral_code, user=user)

        ctx.total_discount = min(subtotal, ctx.coupon_discount + ctx.promotion_discount)
        return ctx

    @classmethod
    @transaction.atomic
    def apply_to_order(cls, order: Order, ctx: GrowthCheckoutContext, *, user=None) -> Order:
        if ctx.error:
            raise CouponError(ctx.error)

        order.discount_amount = ctx.coupon_discount
        order.promotion_discount_amount = ctx.promotion_discount
        order.coupon = ctx.coupon
        order.referral_code_applied = ctx.referral_code if ctx.referral_code_obj else ""

        promo_note = ""
        if ctx.promotion_labels:
            promo_note = " promo:" + ",".join(ctx.promotion_labels)

        order.total = max(
            Decimal("0.00"),
            order.subtotal + order.delivery_fee - ctx.total_discount,
        )
        order.save(
            update_fields=[
                "discount_amount",
                "promotion_discount_amount",
                "coupon",
                "referral_code_applied",
                "total",
                "updated_at",
            ]
        )

        if ctx.referral_code_obj and user:
            ctx.pending_referral = ReferralService.attach_pending_referral(order, ctx.referral_code_obj)

        if promo_note and promo_note not in (order.notes or ""):
            order.notes = (order.notes or "") + promo_note
            order.save(update_fields=["notes", "updated_at"])

        return order

    @classmethod
    @transaction.atomic
    def finalize_on_payment(cls, order: Order) -> dict:
        """Redeem coupons, process referrals, record attribution — called after payment success."""
        from growth.attribution_service import AttributionService

        results = {"coupon": None, "referral": None, "attributions": 0}

        if order.coupon_id:
            results["coupon"] = CouponService.redeem(order.coupon, order, user=order.user)

        results["referral"] = ReferralService.finalize_on_payment(order)
        attributions = AttributionService.record_for_order(order)
        results["attributions"] = len(attributions)

        if order.user_id:
            from growth.clv_service import CLVService

            CLVService.calculate_for_user(order.user)

        return results
