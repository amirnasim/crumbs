"""Unit tests for ReferralService anti-abuse logic."""

import pytest

from accounts.models import CustomerProfile
from growth.models import Referral
from growth.referral_service import ReferralService
from orders.models import Order
from tests.factories import create_order, create_product, create_referral_code, create_user
from loyalty.services import get_or_create_account


@pytest.mark.django_db
class TestReferralService:
    def test_self_referral_blocked(self, referrer):
        referred = referrer
        code = create_referral_code(referrer)
        result = ReferralService.validate_for_checkout(code.code, user=referred)
        assert result is None

    def test_duplicate_referral_blocked(self, referrer, referred_user):
        code = create_referral_code(referrer)
        Referral.objects.create(
            referrer=referrer,
            referred_user=referred_user,
            referral_code=code,
            status=Referral.Status.PENDING,
        )
        result = ReferralService.validate_for_checkout(code.code, user=referred_user)
        assert result is None

    def test_matching_email_blocked_as_self_referral(self, referrer, referred_user):
        referred_user.email = referrer.email
        referred_user.save(update_fields=["email"])
        code = create_referral_code(referrer)
        assert ReferralService.validate_for_checkout(code.code, user=referred_user) is None

    def test_matching_phone_blocked(self, referrer, referred_user):
        CustomerProfile.objects.filter(user=referrer).update(phone="09121111111")
        CustomerProfile.objects.filter(user=referred_user).update(phone="09121111111")
        referrer.profile.refresh_from_db()
        referred_user.profile.refresh_from_db()
        code = create_referral_code(referrer)
        assert ReferralService.validate_for_checkout(code.code, user=referred_user) is None

    def test_valid_referral_accepted(self, referrer, referred_user):
        code = create_referral_code(referrer)
        result = ReferralService.validate_for_checkout(code.code, user=referred_user)
        assert result is not None
        assert result.user_id == referrer.pk

    def test_finalize_rewards_referrer_on_payment(self, referrer, referred_user):
        code = create_referral_code(referrer)
        product = create_product()
        order = create_order(
            referred_user,
            product,
            payment_status=Order.PaymentStatus.PAID,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        order.referral_code_applied = code.code
        order.save(update_fields=["referral_code_applied"])
        referral = ReferralService.attach_pending_referral(order, code)
        assert referral is not None
        result = ReferralService.finalize_on_payment(order)
        assert result.status == Referral.Status.REWARDED
        account = get_or_create_account(referrer)
        account.refresh_from_db()
        assert account.points > 0
