"""Edge cases — duplicate webhooks, repeated submissions, abuse attempts."""

from decimal import Decimal

import pytest
from django.test import override_settings
from django.utils import timezone

from cart.models import Cart
from delivery.services import process_checkout
from growth.coupon_service import CouponService
from growth.referral_service import ReferralService
from notifications.models import SMSLog
from notifications.services import send_template_sms
from orders.exceptions import CheckoutError
from orders.models import Order
from payments.models import PaymentEvent
from payments.services import process_webhook
from tests.factories import CUSTOMER, create_cart_with_item, create_coupon, create_order, create_product, create_referral_code
from tests.mocks.payments import MockPaymentProvider
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS

ZARINPAL_SETTINGS = {
    "DEFAULT_PAYMENT_PROVIDER": "zarinpal",
    "PAYMENT_PROVIDER": "zarinpal",
    "ZARINPAL_MERCHANT_ID": "test-merchant-id",
    "ZARINPAL_SANDBOX": True,
    "ZARINPAL_CALLBACK_URL": "https://example.com/payments/zarinpal/callback/",
    "ONLINE_PAYMENT_CURRENCY": "irr",
}


@pytest.mark.edge_case
@pytest.mark.django_db
class TestDuplicatePaymentWebhook:
    def test_duplicate_webhook_processed_once(self):
        provider = MockPaymentProvider()
        process_webhook(provider, b"{}", "sig")
        process_webhook(provider, b"{}", "sig")
        assert PaymentEvent.objects.filter(event_id="evt_mock_duplicate_test", processed=True).count() == 1
        assert len(provider.events_handled) == 1


@pytest.mark.edge_case
@pytest.mark.django_db
class TestRepeatedOrderSubmission:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_empty_cart_checkout_rejected(self, user, product, mock_stripe_checkout):
        from cart.models import Cart

        cart, _ = Cart.objects.get_or_create(user=user)
        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_duplicate_checkout_returns_existing_in_progress_order(
        self, user, product, mock_stripe_checkout
    ):
        cart = create_cart_with_item(user, product)
        first = process_checkout(cart, CUSTOMER, user=user)
        cart.refresh_from_db()

        assert cart.active_checkout_order_id == first.order.pk
        assert cart.items.count() == 0

        second = process_checkout(cart, CUSTOMER, user=user)
        assert second.order.pk == first.order.pk
        assert Order.objects.filter(user=user).count() == 1

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_locked_cart_total_matches_order_total(self, user, product, mock_stripe_checkout):
        cart = create_cart_with_item(user, product, quantity=2)
        result = process_checkout(cart, CUSTOMER, user=user)

        expected_subtotal = product.price * 2
        assert result.order.subtotal == expected_subtotal
        assert result.order.delivery_fee == Decimal("0.00")
        assert result.order.total == expected_subtotal


@pytest.mark.edge_case
@pytest.mark.django_db
class TestCheckoutCartLocking:
    def test_cart_mutation_blocked_during_checkout(self, user, product, delivery_zone):
        from cart.exceptions import CartMutationBlocked
        from cart.services import add_item, remove_item, set_item_quantity

        cart = create_cart_with_item(user, product)
        order = create_order(
            user,
            product,
            payment_status=Order.PaymentStatus.PENDING_PAYMENT,
            status=Order.Status.PENDING_PAYMENT,
            payment_method=Order.PaymentMethod.ONLINE,
        )
        cart.active_checkout_order = order
        cart.save(update_fields=["active_checkout_order"])

        with pytest.raises(CartMutationBlocked):
            add_item(cart, product, 1)
        with pytest.raises(CartMutationBlocked):
            set_item_quantity(cart, product, 2)
        with pytest.raises(CartMutationBlocked):
            remove_item(cart, product)

    @override_settings(**{
        **ZARINPAL_SETTINGS,
        "DEFAULT_PAYMENT_METHOD": "online",
    })
    def test_failed_online_checkout_releases_active_order(
        self, user, product, mocker
    ):
        from orders.exceptions import CheckoutError
        from payments.exceptions import PaymentError
        from payments.services import PaymentService

        mocker.patch.object(
            PaymentService,
            "initiate_online",
            side_effect=PaymentError("gateway unavailable"),
        )

        cart = create_cart_with_item(user, product)
        with pytest.raises(CheckoutError, match="پرداخت آنلاین"):
            process_checkout(cart, CUSTOMER, user=user)

        cart.refresh_from_db()
        assert cart.active_checkout_order_id is None
        assert Order.objects.filter(user=user).count() == 0

    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_stock_reservation_uses_locked_cart_items(self, user, product, mock_stripe_checkout):
        from inventory.models import StockReservation

        cart = create_cart_with_item(user, product, quantity=3)
        result = process_checkout(cart, CUSTOMER, user=user)

        reservation = StockReservation.objects.filter(order=result.order).first()
        assert reservation is not None
        assert reservation.quantity == 3
        assert result.order.items.first().quantity == 3


@pytest.mark.edge_case
@pytest.mark.django_db
class TestSMSResendAttempts:
    def test_duplicate_sms_blocked_by_dedupe(self, paid_order, sms_templates, mock_sms_provider):
        from notifications.services import send_template_sms

        dedupe = f"{paid_order.pk}:payment_success"
        send_template_sms(
            "payment_success",
            "09121234567",
            {"order_number": paid_order.order_number},
            order=paid_order,
            dedupe_key=dedupe,
        )
        send_template_sms(
            "payment_success",
            "09121234567",
            {"order_number": paid_order.order_number},
            order=paid_order,
            dedupe_key=dedupe,
        )
        sent = SMSLog.objects.filter(order=paid_order, status=SMSLog.Status.SENT).count()
        skipped = SMSLog.objects.filter(order=paid_order, status=SMSLog.Status.SKIPPED).count()
        assert sent == 1
        assert skipped >= 1


@pytest.mark.edge_case
@pytest.mark.django_db
class TestExpiredCartCheckout:
    @override_settings(**STRIPE_ONLINE_SETTINGS)
    def test_stale_cart_item_rejected_when_out_of_stock(self, user, product, mock_stripe_checkout):
        from inventory.models import ProductInventory

        cart = create_cart_with_item(user, product, quantity=1)
        ProductInventory.objects.filter(product=product).update(stock_quantity=0, reserved_quantity=0)
        with pytest.raises(CheckoutError):
            process_checkout(cart, CUSTOMER, user=user)


@pytest.mark.edge_case
@pytest.mark.django_db
class TestInvalidCouponUsage:
    def test_expired_coupon_rejected(self, user):
        coupon = create_coupon(code="OLD")
        coupon.valid_until = timezone.now() - timezone.timedelta(days=1)
        coupon.save(update_fields=["valid_until"])
        result = CouponService.validate("OLD", subtotal=Decimal("100000"), user=user)
        assert result.coupon is None


@pytest.mark.edge_case
@pytest.mark.django_db
class TestReferralAbuse:
    def test_self_referral_at_checkout_blocked(self, referrer):
        code = create_referral_code(referrer)
        assert ReferralService.validate_for_checkout(code.code, user=referrer) is None

    def test_second_referral_for_same_user_blocked(self, referrer, referred_user, product):
        from growth.models import Referral

        code = create_referral_code(referrer)
        order = create_order(referred_user, product)
        ReferralService.attach_pending_referral(order, code)
        assert ReferralService.validate_for_checkout(code.code, user=referred_user) is None
        assert Referral.objects.filter(referred_user=referred_user).count() == 1
