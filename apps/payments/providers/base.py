from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutSessionResult:
    session_id: str
    url: str
    payment_intent_id: str | None = None


@dataclass(frozen=True)
class VerifiedWebhookEvent:
    event_id: str
    event_type: str
    data_object: dict


class PaymentProvider(ABC):
    provider_name: str

    @abstractmethod
    def create_checkout_session(self, order, payment) -> CheckoutSessionResult:
        raise NotImplementedError

    @abstractmethod
    def verify_webhook(self, payload: bytes, signature: str) -> VerifiedWebhookEvent:
        raise NotImplementedError

    @abstractmethod
    def handle_webhook_event(self, event: VerifiedWebhookEvent) -> None:
        raise NotImplementedError
