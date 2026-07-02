import logging

from django.conf import settings
from django.db import IntegrityError, transaction
from django.utils import timezone

from core.observability import log_payment_event
from orders.models import Order
from orders.services.order_service import OrderService
from payments.exceptions import (
    PaymentAmountMismatchError,
    PaymentConfigurationError,
    PaymentError,
    WebhookProcessingError,
)
from payments.models import Payment, PaymentEvent
from payments.providers.base import PaymentProvider

logger = logging.getLogger(__name__)

_SUCCESSFUL_ORDER_PAYMENT_STATUSES = {
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.CASH_RECEIVED,
}


def _order_has_successful_payment(order: Order) -> bool:
    return order.payment_status in _SUCCESSFUL_ORDER_PAYMENT_STATUSES


def get_online_payment_provider() -> PaymentProvider:
    provider = settings.DEFAULT_PAYMENT_PROVIDER
    if provider == Payment.Provider.ZARINPAL:
        from payments.providers.zarinpal import ZarinpalPaymentProvider

        return ZarinpalPaymentProvider()
    if provider == Payment.Provider.STRIPE:
        if not settings.STRIPE_ENABLED:
            raise PaymentConfigurationError(
                "Stripe checkout is disabled. Set STRIPE_ENABLED=True to enable Stripe."
            )
        from payments.providers.stripe import StripePaymentProvider

        return StripePaymentProvider()
    raise PaymentConfigurationError(f"Unsupported online payment provider: {provider}")


class PaymentService:
    """Payment domain service — no direct order mutation outside OrderService."""

    ACTIVE_ONLINE_STATUSES = {Payment.Status.PENDING, Payment.Status.PROCESSING}

    @staticmethod
    def _get_reusable_zarinpal_payment(order: Order) -> Payment | None:
        payment = (
            Payment.objects.filter(
                order=order,
                provider=Payment.Provider.ZARINPAL,
                status=Payment.Status.PROCESSING,
            )
            .exclude(provider_checkout_session_id="")
            .exclude(checkout_url="")
            .order_by("-created_at")
            .first()
        )
        if payment and payment.has_active_zarinpal_checkout:
            return payment
        return None

    @staticmethod
    def initiate_payment(order: Order) -> Payment:
        if order.payment_method == Order.PaymentMethod.COD:
            return PaymentService.initiate_cod(order)
        return PaymentService.initiate_online(order)

    @staticmethod
    @transaction.atomic
    def initiate_online(order: Order) -> Payment:
        order = Order.objects.select_for_update().get(pk=order.pk)

        if order.payment_status in {Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED}:
            raise PaymentError(f"Order {order.order_number} is already paid.")

        currency = settings.ONLINE_PAYMENT_CURRENCY.lower()
        if currency != "irr":
            raise PaymentConfigurationError("Online payments must use IRR currency.")

        provider = get_online_payment_provider()

        if provider.provider_name == Payment.Provider.ZARINPAL:
            existing = PaymentService._get_reusable_zarinpal_payment(order)
            if existing:
                if existing.amount != order.total:
                    raise PaymentAmountMismatchError(
                        "Pending Zarinpal payment amount does not match the current order total."
                    )
                if existing.currency.lower() != currency:
                    raise PaymentConfigurationError("Pending Zarinpal payment currency is invalid.")
                return existing

        payment = Payment.objects.create(
            order=order,
            provider=provider.provider_name,
            status=Payment.Status.PENDING,
            amount=order.total,
            currency=currency,
        )

        session = provider.create_checkout_session(order, payment)
        payment.provider_checkout_session_id = session.session_id
        payment.provider_payment_id = session.payment_intent_id or ""
        payment.checkout_url = session.url
        payment.status = Payment.Status.PROCESSING
        payment.metadata = {
            **payment.metadata,
            "zarinpal_authority": session.session_id,
        }
        payment.save(
            update_fields=[
                "provider_checkout_session_id",
                "provider_payment_id",
                "checkout_url",
                "status",
                "metadata",
                "updated_at",
            ]
        )

        order.payment_status = Order.PaymentStatus.PENDING_PAYMENT
        order.save(update_fields=["payment_status", "updated_at"])
        return payment

    @staticmethod
    @transaction.atomic
    def initiate_cod(order: Order) -> Payment:
        if order.payment_status in {Order.PaymentStatus.CASH_RECEIVED}:
            raise PaymentError(f"Order {order.order_number} is already paid.")

        return Payment.objects.create(
            order=order,
            provider=Payment.Provider.COD,
            status=Payment.Status.PENDING,
            amount=order.total,
            currency="irr",
            metadata={"method": "cash_on_delivery"},
        )

    @staticmethod
    def _counter_provider(payment_method: str) -> str:
        if payment_method == Order.PaymentMethod.CASH:
            return Payment.Provider.CASH
        if payment_method == Order.PaymentMethod.COUNTER_CARD:
            return Payment.Provider.COUNTER_CARD
        raise PaymentError(f"Unsupported counter payment method: {payment_method}")

    @staticmethod
    @transaction.atomic
    def initiate_counter_payment(order: Order, payment_method: str) -> Payment:
        if not order.is_counter_payment:
            raise PaymentError("Order is not a counter payment order.")
        if order.status != Order.Status.AWAITING_PAYMENT:
            raise PaymentError("Counter payment can only be initiated for awaiting-payment orders.")

        provider = PaymentService._counter_provider(payment_method)
        existing = (
            Payment.objects.filter(order=order, provider=provider)
            .exclude(status=Payment.Status.CANCELLED)
            .order_by("-created_at")
            .first()
        )
        if existing:
            return existing

        return Payment.objects.create(
            order=order,
            provider=provider,
            status=Payment.Status.PENDING,
            amount=order.total,
            currency="irr",
            metadata={"method": payment_method},
        )

    @staticmethod
    @transaction.atomic
    def mark_counter_cash_received(order: Order, payment: Payment, *, actor: str = "admin") -> Order:
        return PaymentService._mark_counter_payment_received(
            order,
            payment,
            expected_provider=Payment.Provider.CASH,
            actor=actor,
        )

    @staticmethod
    @transaction.atomic
    def mark_counter_card_received(order: Order, payment: Payment, *, actor: str = "admin") -> Order:
        return PaymentService._mark_counter_payment_received(
            order,
            payment,
            expected_provider=Payment.Provider.COUNTER_CARD,
            actor=actor,
        )

    @staticmethod
    @transaction.atomic
    def _mark_counter_payment_received(
        order: Order,
        payment: Payment,
        *,
        expected_provider: str,
        actor: str = "admin",
    ) -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.provider != expected_provider:
            raise PaymentError("Payment provider does not match the requested counter action.")
        if payment.order_id != order.pk:
            raise PaymentError("Payment does not belong to this order.")
        if not order.is_counter_payment:
            raise PaymentError("This action is only valid for counter payment orders.")
        if order.status != Order.Status.AWAITING_PAYMENT and payment.status == Payment.Status.SUCCEEDED:
            return order

        if payment.status == Payment.Status.SUCCEEDED:
            if order.status == Order.Status.PREPARING:
                return order
            return OrderService.finalize_counter_payment(order, actor=actor)

        metadata = dict(payment.metadata or {})
        metadata["counter_payment_event"] = "counter_payment_received"
        metadata["counter_payment_actor"] = actor
        payment.status = Payment.Status.SUCCEEDED
        payment.failure_message = ""
        payment.metadata = metadata
        payment.save(
            update_fields=["status", "failure_message", "metadata", "updated_at"]
        )
        return OrderService.finalize_counter_payment(order, actor=actor)

    @staticmethod
    @transaction.atomic
    def mark_paid(order: Order, payment: Payment) -> None:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.status == Payment.Status.SUCCEEDED:
            return

        if _order_has_successful_payment(order):
            payment.status = Payment.Status.SUCCEEDED
            payment.failure_message = ""
            payment.save(update_fields=["status", "failure_message", "updated_at"])
            return

        payment.status = Payment.Status.SUCCEEDED
        payment.failure_message = ""
        payment.save(update_fields=["status", "failure_message", "updated_at"])
        log_payment_event(
            "payment_verified",
            order_id=order.pk,
            payment_id=payment.pk,
            provider=payment.provider,
            status=payment.status,
        )
        OrderService.finalize_online_payment(order)

    @staticmethod
    @transaction.atomic
    def mark_cod_cash_received(order: Order, payment: Payment, *, actor: str = "admin") -> Order:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.provider != Payment.Provider.COD:
            raise PaymentError("This action is only valid for COD payments.")
        if payment.order_id != order.pk:
            raise PaymentError("Payment does not belong to this order.")

        if order.payment_status != Order.PaymentStatus.CASH_RECEIVED:
            order.payment_status = Order.PaymentStatus.CASH_RECEIVED
            order.save(update_fields=["payment_status", "updated_at"])

        return PaymentService.ensure_cod_cash_finalized(order, payment=payment, actor=actor)

    @staticmethod
    @transaction.atomic
    def ensure_cod_cash_finalized(
        order: Order,
        *,
        payment: Payment | None = None,
        actor: str = "admin",
    ) -> Order:
        """Idempotently mark COD payment complete and consume inventory."""
        order = Order.objects.select_for_update().get(pk=order.pk)
        if not order.is_cod or order.payment_status != Order.PaymentStatus.CASH_RECEIVED:
            return order

        if payment is None:
            payment = (
                Payment.objects.select_for_update()
                .filter(order=order, provider=Payment.Provider.COD)
                .order_by("-created_at")
                .first()
            )
        else:
            payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment is None:
            return order

        if payment.status != Payment.Status.SUCCEEDED:
            metadata = dict(payment.metadata or {})
            metadata["cash_received_event"] = "cod_cash_finalized"
            metadata["cash_received_actor"] = actor
            payment.status = Payment.Status.SUCCEEDED
            payment.failure_message = ""
            payment.metadata = metadata
            payment.save(
                update_fields=["status", "failure_message", "metadata", "updated_at"]
            )

        return OrderService.record_cash_received(order, actor=actor)

    @staticmethod
    @transaction.atomic
    def mark_failed(order: Order, payment: Payment, message: str) -> None:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.status == Payment.Status.SUCCEEDED:
            return
        if _order_has_successful_payment(order):
            return

        payment.status = Payment.Status.FAILED
        payment.failure_message = message
        payment.save(update_fields=["status", "failure_message", "updated_at"])
        log_payment_event(
            "payment_failed",
            order_id=order.pk,
            payment_id=payment.pk,
            provider=payment.provider,
            status=payment.status,
            outcome="failed",
        )
        OrderService.mark_payment_failed(order, reason=message, actor="payment_webhook")

    @staticmethod
    @transaction.atomic
    def mark_cancelled(order: Order, payment: Payment, message: str) -> None:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = Payment.objects.select_for_update().get(pk=payment.pk)

        if payment.status == Payment.Status.SUCCEEDED:
            return
        if _order_has_successful_payment(order):
            return

        payment.status = Payment.Status.CANCELLED
        payment.failure_message = message
        payment.save(update_fields=["status", "failure_message", "updated_at"])

        if order.payment_status not in {
            Order.PaymentStatus.PAID,
            Order.PaymentStatus.CASH_RECEIVED,
        }:
            order.payment_status = Order.PaymentStatus.PENDING_PAYMENT
            order.save(update_fields=["payment_status", "updated_at"])

    @staticmethod
    @transaction.atomic
    def process_refund(order: Order) -> None:
        order = Order.objects.select_for_update().get(pk=order.pk)
        payment = order.payments.order_by("-created_at").first()
        if payment and payment.status == Payment.Status.SUCCEEDED:
            payment.status = Payment.Status.REFUNDED
            payment.save(update_fields=["status", "updated_at"])


# Backward-compatible module-level aliases
initiate_payment = PaymentService.initiate_payment
initiate_online_payment = PaymentService.initiate_online
initiate_cod_payment = PaymentService.initiate_cod
mark_order_paid = PaymentService.mark_paid
mark_cod_collected = PaymentService.mark_cod_cash_received
mark_counter_cash_collected = PaymentService.mark_counter_cash_received
mark_counter_card_collected = PaymentService.mark_counter_card_received
mark_order_payment_failed = PaymentService.mark_failed
mark_order_payment_cancelled = PaymentService.mark_cancelled
mark_order_refunded = PaymentService.process_refund


@transaction.atomic
def process_webhook(provider: PaymentProvider, payload: bytes, signature: str) -> PaymentEvent:
    event = provider.verify_webhook(payload, signature)
    payload_data = {
        "id": event.event_id,
        "type": event.event_type,
        "object": event.data_object,
    }

    try:
        payment_event, _created = PaymentEvent.objects.get_or_create(
            event_id=event.event_id,
            defaults={
                "provider": provider.provider_name,
                "event_type": event.event_type,
                "payload": payload_data,
            },
        )
    except IntegrityError:
        payment_event = PaymentEvent.objects.get(event_id=event.event_id)

    payment_event = PaymentEvent.objects.select_for_update().get(pk=payment_event.pk)
    if payment_event.processed:
        return payment_event

    log_payment_event(
        "payment_callback_received",
        provider=provider.provider_name,
        status=event.event_type,
    )

    try:
        provider.handle_webhook_event(event)
    except Exception as exc:
        payment_event.processing_error = str(exc)
        payment_event.save(update_fields=["processing_error"])
        log_payment_event(
            "payment_callback_failed",
            provider=provider.provider_name,
            status="error",
            outcome=event.event_type,
        )
        logger.exception("Webhook processing failed for %s", event.event_id)
        raise WebhookProcessingError(str(exc)) from exc

    payment_event.processed = True
    payment_event.processed_at = timezone.now()
    payment_event.processing_error = ""
    payment_event.save(update_fields=["processed", "processed_at", "processing_error"])
    log_payment_event(
        "payment_callback_processed",
        provider=provider.provider_name,
        status="ok",
        outcome=event.event_type,
    )
    return payment_event


def handle_stripe_webhook(payload: bytes, signature: str) -> PaymentEvent:
    from django.conf import settings as django_settings

    if not django_settings.STRIPE_ENABLED:
        raise PaymentConfigurationError(
            "Stripe webhooks are disabled. Set STRIPE_ENABLED=True to enable Stripe."
        )

    from payments.providers.stripe import StripePaymentProvider

    provider = StripePaymentProvider()
    return process_webhook(provider, payload, signature)


def handle_zarinpal_callback(payload: bytes) -> PaymentEvent:
    from payments.providers.zarinpal import ZarinpalPaymentProvider

    provider = ZarinpalPaymentProvider()
    return process_webhook(provider, payload, signature="")
