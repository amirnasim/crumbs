"""Mock helpers for external services."""

from unittest.mock import MagicMock

from notifications.providers.base import SMSResult
from payments.providers.base import CheckoutSessionResult, VerifiedWebhookEvent


class MockSMSProvider:
    provider_name = "mock"

    def __init__(self):
        self.send = MagicMock(return_value=SMSResult(success=True, message_id="mock-001"))
        self.calls = self.send.call_args_list


def mock_checkout_session(**kwargs):
    defaults = {
        "session_id": "cs_test_mock",
        "url": "https://checkout.example.com/mock",
        "payment_intent_id": "pi_test_mock",
    }
    defaults.update(kwargs)
    return CheckoutSessionResult(**defaults)


def mock_stripe_webhook_event(*, event_id="evt_test_1", event_type="checkout.session.completed", payment_id=1):
    return VerifiedWebhookEvent(
        event_id=event_id,
        event_type=event_type,
        data_object={
            "id": "cs_test",
            "metadata": {"payment_id": str(payment_id)},
        },
    )
