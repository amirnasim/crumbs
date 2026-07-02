"""Payment provider mocks."""

from payments.providers.base import CheckoutSessionResult, PaymentProvider, VerifiedWebhookEvent


class MockPaymentProvider(PaymentProvider):
    provider_name = "mock_stripe"

    def __init__(self):
        self.sessions_created = []
        self.events_handled = []

    def create_checkout_session(self, order, payment):
        result = CheckoutSessionResult(
            session_id=f"cs_mock_{payment.pk}",
            url="https://checkout.mock/pay",
            payment_intent_id=f"pi_mock_{payment.pk}",
        )
        self.sessions_created.append((order.pk, payment.pk))
        return result

    def verify_webhook(self, payload: bytes, signature: str):
        return VerifiedWebhookEvent(
            event_id="evt_mock_duplicate_test",
            event_type="checkout.session.completed",
            data_object={"metadata": {}},
        )

    def handle_webhook_event(self, event: VerifiedWebhookEvent) -> None:
        self.events_handled.append(event.event_id)
