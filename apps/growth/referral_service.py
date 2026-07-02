"""Referral code generation, tracking, and reward processing."""

import secrets
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone

from growth.models import Coupon, Referral, ReferralCode
from loyalty.models import LoyaltyAccount, LoyaltyTransaction
from loyalty.services import get_or_create_account
from orders.models import Order

User = get_user_model()


class ReferralError(Exception):
    pass


class ReferralService:
    PAID_STATUSES = {Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED}

    @staticmethod
    def _generate_code() -> str:
        for _ in range(10):
            code = secrets.token_hex(4).upper()
            if not ReferralCode.objects.filter(code=code).exists():
                return code
        raise ReferralError("Unable to generate referral code.")

    @classmethod
    def get_or_create_code(cls, user) -> ReferralCode:
        existing = ReferralCode.objects.filter(user=user).first()
        if existing:
            return existing
        return ReferralCode.objects.create(user=user, code=cls._generate_code())

    @classmethod
    def validate_for_checkout(cls, code: str, *, user) -> ReferralCode | None:
        if not code or not user:
            return None

        normalized = code.strip().upper()
        try:
            referral_code = ReferralCode.objects.select_related("user").get(code__iexact=normalized, is_active=True)
        except ReferralCode.DoesNotExist:
            return None

        if referral_code.user_id == user.pk:
            return None

        if Referral.objects.filter(referred_user=user).exists():
            return None

        if cls._is_likely_self_referral(referral_code.user, user):
            return None

        return referral_code

    @staticmethod
    def _is_likely_self_referral(referrer, referred) -> bool:
        if referrer.email and referred.email and referrer.email.lower() == referred.email.lower():
            return True
        ref_phone = getattr(getattr(referrer, "profile", None), "phone", "")
        new_phone = getattr(getattr(referred, "profile", None), "phone", "")
        return bool(ref_phone and new_phone and ref_phone == new_phone)

    @classmethod
    @transaction.atomic
    def attach_pending_referral(cls, order: Order, referral_code: ReferralCode) -> Referral | None:
        if not order.user_id:
            return None

        if Referral.objects.filter(referred_user=order.user).exists():
            return None

        return Referral.objects.create(
            referrer=referral_code.user,
            referred_user=order.user,
            referral_code=referral_code,
            status=Referral.Status.PENDING,
        )

    @classmethod
    @transaction.atomic
    def finalize_on_payment(cls, order: Order) -> Referral | None:
        if not order.user_id or order.payment_status not in cls.PAID_STATUSES:
            return None

        referral = (
            Referral.objects.select_related("referrer", "referral_code")
            .filter(referred_user=order.user, status=Referral.Status.PENDING)
            .first()
        )
        if referral is None and order.referral_code_applied:
            try:
                code = ReferralCode.objects.get(code__iexact=order.referral_code_applied)
            except ReferralCode.DoesNotExist:
                return None
            referral = cls.attach_pending_referral(order, code)

        if referral is None:
            return None

        referral.first_order = order
        referral.status = Referral.Status.COMPLETED
        referral.save(update_fields=["first_order", "status", "rewarded_at"])

        referrer_points = getattr(settings, "REFERRAL_REWARD_POINTS", 100)
        referred_coupon_code = getattr(settings, "REFERRAL_ONBOARDING_COUPON", "")

        account = get_or_create_account(referral.referrer)
        account.points += referrer_points
        account.lifetime_points += referrer_points
        account.save(update_fields=["points", "lifetime_points", "updated_at"])
        LoyaltyTransaction.objects.create(
            account=account,
            transaction_type=LoyaltyTransaction.Type.EARN,
            points=referrer_points,
            balance_after=account.points,
            order=order,
            description=f"Referral reward for order {order.order_number}",
        )

        referral.referrer_reward_points = referrer_points
        if referred_coupon_code:
            from growth.coupon_service import CouponService

            coupon = Coupon.objects.filter(code__iexact=referred_coupon_code, is_active=True).first()
            if coupon:
                referral.referred_discount_amount = CouponService.calculate_discount(coupon, order.subtotal)
        referral.status = Referral.Status.REWARDED
        referral.rewarded_at = timezone.now()
        referral.save(
            update_fields=[
                "referrer_reward_points",
                "referred_discount_amount",
                "status",
                "rewarded_at",
            ]
        )
        return referral
