"""Flow D: Referral signup → first order → reward → attribution tracking."""

import pytest
from django.test import override_settings

from delivery.services import process_checkout
from growth.attribution_service import AttributionService
from growth.checkout_integration import GrowthCheckoutFacade
from growth.models import Referral
from growth.referral_service import ReferralService
from orders.models import Order
from payments.services import PaymentService
from tests.factories import CUSTOMER, create_cart_with_item, create_referral_code
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


@pytest.mark.integration
@pytest.mark.django_db
class TestReferralFlow:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_referral_reward_and_attribution(
        self, referrer, referred_user, product, delivery_zone, mock_stripe_checkout, mocker
    ):
        code = create_referral_code(referrer)
        cart = create_cart_with_item(referred_user, product)
        cart.referral_code = code.code
        cart.save(update_fields=["referral_code"])

        result = process_checkout(cart, CUSTOMER, user=referred_user)
        order = result.order
        assert order.referral_code_applied == code.code

        mocker.patch("growth.signals.emit_order_lifecycle_events")
        PaymentService.mark_paid(order, result.payment)
        order.refresh_from_db()
        assert order.payment_status == Order.PaymentStatus.PAID

        GrowthCheckoutFacade.finalize_on_payment(order)
        referral = Referral.objects.get(referred_user=referred_user)
        assert referral.status == Referral.Status.REWARDED
        assert referral.first_order_id == order.pk

        attributions = AttributionService.record_for_order(order)
        assert len(attributions) >= 1
