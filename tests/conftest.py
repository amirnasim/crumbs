"""Shared pytest fixtures for CRUMBS test suite."""

import os

import pytest
from django.test import override_settings

from tests.factories import (
    create_cart_with_item,
    create_coupon,
    create_delivery_zone,
    create_order,
    create_product,
    create_user,
    seed_sms_templates,
)


def _zarinpal_integration_enabled() -> bool:
    return bool(os.environ.get("ZARINPAL_MERCHANT_ID", "").strip())


@pytest.fixture(autouse=True)
def _gate_zarinpal_integration_tests(request):
    if request.node.get_closest_marker("zarinpal_integration") is None:
        yield
        return
    if not _zarinpal_integration_enabled():
        pytest.skip(
            "Zarinpal integration tests require ZARINPAL_MERCHANT_ID in the environment."
        )
    yield


@pytest.fixture(autouse=True)
def _test_settings():
    with override_settings(
        CELERY_TASK_ALWAYS_EAGER=True,
        CELERY_TASK_EAGER_PROPAGATES=True,
        SMS_PROVIDER="console",
    ):
        yield


@pytest.fixture
def delivery_zone(db):
    return create_delivery_zone()


@pytest.fixture
def product(db):
    return create_product(stock_quantity=20)


@pytest.fixture
def low_stock_product(db):
    return create_product(stock_quantity=2, name="Limited Cookie")


@pytest.fixture
def user(db):
    return create_user()


@pytest.fixture
def referrer(db):
    return create_user(username="referrer", email="referrer@example.com")


@pytest.fixture
def referred_user(db):
    return create_user(username="referred", email="referred@example.com")


@pytest.fixture
def cart_with_item(db, user, product):
    return create_cart_with_item(user, product, quantity=1)


@pytest.fixture
def coupon(db):
    return create_coupon(code="SAVE10", discount_value=10)


@pytest.fixture
def first_order_coupon(db):
    from growth.models import Coupon

    return create_coupon(
        code="FIRST10",
        discount_value=10,
        campaign_type=Coupon.CampaignType.FIRST_ORDER,
    )


@pytest.fixture
def sms_templates(db):
    return seed_sms_templates()


@pytest.fixture
def paid_order(db, user, product, delivery_zone):
    from orders.models import Order

    return create_order(
        user,
        product,
        payment_status=Order.PaymentStatus.PAID,
        status=Order.Status.PAID,
    )


@pytest.fixture
def mock_stripe_checkout(mocker):
    from payments.providers.base import CheckoutSessionResult

    return mocker.patch(
        "payments.providers.stripe.StripePaymentProvider.create_checkout_session",
        return_value=CheckoutSessionResult(
            session_id="cs_test_123",
            url="https://checkout.stripe.com/test",
            payment_intent_id="pi_test_123",
        ),
    )


@pytest.fixture
def mock_sms_provider(mocker):
    from notifications.providers.base import SMSResult

    provider = mocker.MagicMock()
    provider.send.return_value = SMSResult(success=True, message_id="mock-sms-id")
    mocker.patch(
        "notifications.services.get_sms_provider",
        return_value=provider,
    )
    return provider
