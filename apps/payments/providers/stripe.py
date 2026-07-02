import logging

import stripe
from django.conf import settings
from django.db import transaction

from payments.exceptions import PaymentConfigurationError, PaymentProviderError, WebhookVerificationError
from payments.models import Payment
from orders.models import Order

from .base import CheckoutSessionResult, PaymentProvider, VerifiedWebhookEvent

logger = logging.getLogger(__name__)


class StripePaymentProvider(PaymentProvider):
    provider_name = Payment.Provider.STRIPE

    def __init__(self):
        if not settings.STRIPE_ENABLED:
            raise PaymentConfigurationError(
                "Stripe checkout is disabled. Set STRIPE_ENABLED=True to enable Stripe."
            )
        if not settings.STRIPE_SECRET_KEY:
            raise PaymentConfigurationError("STRIPE_SECRET_KEY is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY

    def create_checkout_session(self, order, payment) -> CheckoutSessionResult:
        if not settings.STRIPE_ENABLED:
            raise PaymentConfigurationError(
                "Stripe checkout is disabled. Set STRIPE_ENABLED=True to enable Stripe."
            )
        line_items = []
        for item in order.items.all():
            line_items.append(
                {
                    "price_data": {
                        "currency": payment.currency,
                        "unit_amount": int(item.unit_price * 100),
                        "product_data": {"name": item.product_name},
                    },
                    "quantity": item.quantity,
                }
            )

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                line_items=line_items,
                success_url=settings.PAYMENT_SUCCESS_URL,
                cancel_url=settings.PAYMENT_CANCEL_URL,
                customer_email=order.email,
                client_reference_id=order.order_number,
                metadata={
                    "order_number": order.order_number,
                    "payment_id": str(payment.pk),
                },
                payment_intent_data={
                    "metadata": {
                        "order_number": order.order_number,
                        "payment_id": str(payment.pk),
                    }
                },
            )
        except stripe.StripeError as exc:
            raise PaymentProviderError(str(exc)) from exc

        payment_intent_id = session.payment_intent
        if isinstance(payment_intent_id, stripe.PaymentIntent):
            payment_intent_id = payment_intent_id.id

        return CheckoutSessionResult(
            session_id=session.id,
            url=session.url,
            payment_intent_id=payment_intent_id,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> VerifiedWebhookEvent:
        if not settings.STRIPE_WEBHOOK_SECRET:
            raise PaymentConfigurationError("STRIPE_WEBHOOK_SECRET is not configured.")
        if not signature:
            raise WebhookVerificationError("Missing Stripe-Signature header.")

        try:
            event = stripe.Webhook.construct_event(
                payload,
                signature,
                settings.STRIPE_WEBHOOK_SECRET,
            )
        except stripe.SignatureVerificationError as exc:
            raise WebhookVerificationError("Invalid Stripe webhook signature.") from exc
        except ValueError as exc:
            raise WebhookVerificationError("Invalid Stripe webhook payload.") from exc

        return VerifiedWebhookEvent(
            event_id=event["id"],
            event_type=event["type"],
            data_object=event["data"]["object"],
        )

    def handle_webhook_event(self, event: VerifiedWebhookEvent) -> None:
        handlers = {
            "checkout.session.completed": self._handle_checkout_completed,
            "checkout.session.expired": self._handle_checkout_expired,
            "payment_intent.payment_failed": self._handle_payment_failed,
            "charge.refunded": self._handle_charge_refunded,
        }
        handler = handlers.get(event.event_type)
        if handler is None:
            logger.info("Unhandled Stripe event type: %s", event.event_type)
            return
        handler(event)

    def _get_payment_from_event(self, data_object: dict) -> Payment:
        payment_id = data_object.get("metadata", {}).get("payment_id")
        if payment_id:
            return Payment.objects.select_related("order").get(pk=payment_id)

        if data_object.get("object") == "checkout.session":
            session_id = data_object.get("id")
        else:
            session_id = data_object.get("checkout_session")

        if session_id:
            return Payment.objects.select_related("order").get(
                provider_checkout_session_id=session_id
            )

        order_number = data_object.get("metadata", {}).get("order_number") or data_object.get(
            "client_reference_id"
        )
        if order_number:
            return (
                Payment.objects.select_related("order")
                .filter(order__order_number=order_number, provider=Payment.Provider.STRIPE)
                .latest("created_at")
            )

        raise PaymentProviderError("Unable to resolve payment from Stripe webhook event.")

    def _handle_checkout_completed(self, event: VerifiedWebhookEvent) -> None:
        from payments.services import mark_order_paid

        data = event.data_object
        payment = self._get_payment_from_event(data)

        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
            order = payment.order

            if payment.status == Payment.Status.SUCCEEDED:
                return
            if order.payment_status in {
                Order.PaymentStatus.PAID,
                Order.PaymentStatus.CASH_RECEIVED,
            }:
                payment.status = Payment.Status.SUCCEEDED
                payment.failure_message = ""
                payment.save(update_fields=["status", "failure_message", "updated_at"])
                return

            payment_intent_id = data.get("payment_intent")
            if isinstance(payment_intent_id, dict):
                payment_intent_id = payment_intent_id.get("id")

            payment.provider_checkout_session_id = data.get("id", payment.provider_checkout_session_id)
            payment.provider_payment_id = payment_intent_id or payment.provider_payment_id
            payment.save(
                update_fields=[
                    "provider_checkout_session_id",
                    "provider_payment_id",
                    "updated_at",
                ]
            )
            mark_order_paid(order, payment)

    def _handle_checkout_expired(self, event: VerifiedWebhookEvent) -> None:
        from payments.services import mark_order_payment_cancelled

        payment = self._get_payment_from_event(event.data_object)
        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
            if payment.status == Payment.Status.SUCCEEDED:
                return
            mark_order_payment_cancelled(payment.order, payment, "Checkout session expired.")

    def _handle_payment_failed(self, event: VerifiedWebhookEvent) -> None:
        from payments.services import mark_order_payment_failed

        data = event.data_object
        payment = self._get_payment_from_event(data)

        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
            order = payment.order

            if payment.status == Payment.Status.SUCCEEDED:
                return
            if order.payment_status in {
                Order.PaymentStatus.PAID,
                Order.PaymentStatus.CASH_RECEIVED,
            }:
                return

            failure_message = data.get("last_payment_error", {}).get("message", "Payment failed.")
            payment.provider_payment_id = data.get("id", payment.provider_payment_id)
            payment.save(update_fields=["provider_payment_id", "updated_at"])
            mark_order_payment_failed(order, payment, failure_message)

    def _handle_charge_refunded(self, event: VerifiedWebhookEvent) -> None:
        from orders.services.order_service import OrderService

        payment_intent_id = event.data_object.get("payment_intent")
        payment = Payment.objects.select_related("order").get(provider_payment_id=payment_intent_id)
        OrderService.process_refund(payment.order, reason="Stripe refund", actor="stripe_webhook")
