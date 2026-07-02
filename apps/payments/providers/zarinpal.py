import json
import logging
import re

import requests
from django.conf import settings
from django.db import transaction

from payments.exceptions import (
    PaymentAmountMismatchError,
    PaymentConfigurationError,
    PaymentProviderError,
    WebhookVerificationError,
)
from orders.models import Order
from payments.models import Payment

from .base import CheckoutSessionResult, PaymentProvider, VerifiedWebhookEvent

logger = logging.getLogger(__name__)

ZARINPAL_MIN_AMOUNT_IRR = 1000
ZARINPAL_SUCCESS_CODE = 100
_SENSITIVE_JSON_KEYS = frozenset(
    {
        "merchant_id",
        "merchant",
        "authorization",
        "password",
        "secret",
        "api_key",
        "access_token",
        "refresh_token",
    }
)
_RESPONSE_BODY_MAX_LENGTH = 2000


def _sanitize_json(value):
    if isinstance(value, dict):
        return {
            key: (
                "***"
                if str(key).lower() in _SENSITIVE_JSON_KEYS
                else _sanitize_json(nested)
            )
            for key, nested in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_json(item) for item in value]
    return value


def _redact_secrets_in_text(text: str) -> str:
    merchant_id = getattr(settings, "ZARINPAL_MERCHANT_ID", "") or ""
    if merchant_id:
        text = text.replace(merchant_id, "***")
    return re.sub(
        r'(?i)("merchant_id"\s*:\s*")([^"]*)(")',
        r'\1***\3',
        text,
    )


def _read_response_body(response: requests.Response, *, max_length: int = _RESPONSE_BODY_MAX_LENGTH) -> str:
    content_type = (response.headers.get("Content-Type") or "").lower()
    if "json" in content_type:
        try:
            text = json.dumps(_sanitize_json(response.json()), ensure_ascii=False)
        except (ValueError, json.JSONDecodeError):
            text = _redact_secrets_in_text((response.text or "").strip())
    else:
        text = _redact_secrets_in_text((response.text or "").strip())

    if not text:
        return "(empty response body)"
    if len(text) > max_length:
        return f"{text[:max_length]}..."
    return text


class ZarinpalPaymentProvider(PaymentProvider):
    """Primary online payment provider for Iran (Zarinpal REST API v4)."""

    provider_name = Payment.Provider.ZARINPAL

    def __init__(self):
        if not settings.ZARINPAL_MERCHANT_ID:
            raise PaymentConfigurationError("ZARINPAL_MERCHANT_ID is not configured.")

    @property
    def _api_base(self) -> str:
        if settings.ZARINPAL_SANDBOX:
            return "https://sandbox.zarinpal.com"
        return "https://api.zarinpal.com"

    @staticmethod
    def validate_order_payment_amount(order, payment) -> int:
        """Ensure payment record matches the final order total in IRR."""
        currency = (payment.currency or "").lower()
        if currency != "irr":
            raise PaymentProviderError("Zarinpal payments must use IRR currency.")

        order_total = int(order.total)
        payment_amount = int(payment.amount)
        if payment_amount != order_total:
            raise PaymentAmountMismatchError(
                f"Payment amount {payment_amount} does not match order total {order_total}."
            )

        if order_total < ZARINPAL_MIN_AMOUNT_IRR:
            raise PaymentProviderError(
                f"Zarinpal minimum payment amount is {ZARINPAL_MIN_AMOUNT_IRR} IRR."
            )

        return order_total

    def create_checkout_session(self, order, payment) -> CheckoutSessionResult:
        amount_rials = self.validate_order_payment_amount(order, payment)
        return self._request_payment(order, payment, amount_rials)

    def _request_payment(self, order, payment, amount_rials: int) -> CheckoutSessionResult:
        callback_url = settings.ZARINPAL_CALLBACK_URL or settings.PAYMENT_SUCCESS_URL
        if not callback_url:
            raise PaymentConfigurationError("ZARINPAL_CALLBACK_URL is not configured.")

        description = f"CRUMBS order {order.order_number}"
        endpoint = f"{self._api_base}/pg/v4/payment/request.json"
        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": amount_rials,
            "callback_url": callback_url,
            "description": description,
            "metadata": {
                "order_number": order.order_number,
                "payment_id": str(payment.pk),
            },
        }
        debug_context = {
            "amount": amount_rials,
            "callback_url": callback_url,
            "description_length": len(description),
            "endpoint": endpoint,
            "sandbox": settings.ZARINPAL_SANDBOX,
            "merchant_id_configured": bool(settings.ZARINPAL_MERCHANT_ID),
        }

        try:
            response = requests.post(
                endpoint,
                json=payload,
                timeout=30,
            )
        except requests.RequestException as exc:
            logger.error(
                "Zarinpal payment request transport error",
                extra={**debug_context, "error": str(exc)},
            )
            raise PaymentProviderError(f"Zarinpal request failed: {exc}") from exc

        if not response.ok:
            response_body = _read_response_body(response)
            logger.error(
                "Zarinpal payment request HTTP error",
                extra={
                    **debug_context,
                    "status_code": response.status_code,
                    "response_body": response_body,
                },
            )
            raise PaymentProviderError(
                f"Zarinpal request failed with HTTP {response.status_code}: {response_body}"
            )

        try:
            body = response.json()
        except json.JSONDecodeError as exc:
            response_body = _read_response_body(response)
            logger.error(
                "Zarinpal payment request returned invalid JSON",
                extra={**debug_context, "response_body": response_body},
            )
            raise PaymentProviderError(
                f"Zarinpal request returned invalid JSON: {response_body}"
            ) from exc

        errors = body.get("errors") or []
        if errors:
            message = errors[0].get("message", "Zarinpal payment request rejected.")
            raise PaymentProviderError(message)

        data = body.get("data") or {}
        if data.get("code") != ZARINPAL_SUCCESS_CODE:
            raise PaymentProviderError(f"Zarinpal returned code {data.get('code')}.")

        authority = data["authority"]
        checkout_url = f"{self._api_base}/pg/StartPay/{authority}"
        return CheckoutSessionResult(
            session_id=authority,
            url=checkout_url,
            payment_intent_id=authority,
        )

    def verify_webhook(self, payload: bytes, signature: str) -> VerifiedWebhookEvent:
        """Parse and validate Zarinpal callback payload."""
        if not payload:
            raise WebhookVerificationError("Missing Zarinpal callback payload.")

        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WebhookVerificationError("Invalid Zarinpal callback payload.") from exc

        authority = data.get("authority") or data.get("Authority")
        status = data.get("status") or data.get("Status")
        payment_id = data.get("payment_id")

        if not authority:
            raise WebhookVerificationError("Missing Zarinpal authority in callback.")

        event_id = f"zarinpal:authority:{authority}"
        return VerifiedWebhookEvent(
            event_id=event_id,
            event_type="payment.callback",
            data_object={
                "authority": authority,
                "status": status,
                "payment_id": payment_id,
            },
        )

    def handle_webhook_event(self, event: VerifiedWebhookEvent) -> None:
        from payments.services import mark_order_paid, mark_order_payment_failed

        data = event.data_object
        status = str(data.get("status", "")).upper()
        authority = data["authority"]

        payment = self._resolve_payment(data, authority)

        with transaction.atomic():
            payment = Payment.objects.select_for_update().select_related("order").get(pk=payment.pk)
            order = payment.order

            if payment.status == Payment.Status.SUCCEEDED:
                logger.info("Ignoring duplicate Zarinpal callback for paid payment %s", payment.pk)
                return

            if order.payment_status in {
                Order.PaymentStatus.PAID,
                Order.PaymentStatus.CASH_RECEIVED,
            }:
                if payment.status != Payment.Status.SUCCEEDED:
                    payment.status = Payment.Status.SUCCEEDED
                    payment.failure_message = ""
                    payment.save(update_fields=["status", "failure_message", "updated_at"])
                logger.info(
                    "Ignoring Zarinpal callback for already-paid order %s",
                    order.pk,
                )
                return

            if status != "OK":
                mark_order_payment_failed(
                    order,
                    payment,
                    "Zarinpal payment was not completed.",
                )
                return

            try:
                ref_id = self._verify_payment(order, payment, authority)
            except PaymentProviderError as exc:
                mark_order_payment_failed(order, payment, str(exc))
                return

            payment.provider_checkout_session_id = authority
            payment.provider_payment_id = str(ref_id)
            payment.metadata = {
                **payment.metadata,
                "zarinpal_authority": authority,
                "zarinpal_ref_id": ref_id,
            }
            payment.save(
                update_fields=[
                    "provider_checkout_session_id",
                    "provider_payment_id",
                    "metadata",
                    "updated_at",
                ]
            )
            mark_order_paid(order, payment)

    def _resolve_payment(self, data: dict, authority: str) -> Payment:
        payment_id = data.get("payment_id")
        if payment_id:
            return Payment.objects.select_related("order").get(
                pk=payment_id,
                provider=Payment.Provider.ZARINPAL,
            )

        return Payment.objects.select_related("order").get(
            provider=Payment.Provider.ZARINPAL,
            provider_checkout_session_id=authority,
        )

    def _verify_payment(self, order, payment: Payment, authority: str) -> int:
        amount_rials = self.validate_order_payment_amount(order, payment)

        payload = {
            "merchant_id": settings.ZARINPAL_MERCHANT_ID,
            "amount": amount_rials,
            "authority": authority,
        }

        try:
            response = requests.post(
                f"{self._api_base}/pg/v4/payment/verify.json",
                json=payload,
                timeout=30,
            )
            response.raise_for_status()
            body = response.json()
        except requests.RequestException as exc:
            raise PaymentProviderError(f"Zarinpal verify failed: {exc}") from exc

        errors = body.get("errors") or []
        if errors:
            message = errors[0].get("message", "Zarinpal verification rejected.")
            raise PaymentProviderError(message)

        data = body.get("data") or {}
        if data.get("code") != ZARINPAL_SUCCESS_CODE:
            raise PaymentProviderError(f"Zarinpal verify returned code {data.get('code')}.")

        ref_id = int(data.get("ref_id") or 0)
        if ref_id <= 0:
            raise PaymentProviderError("Zarinpal verify response missing ref_id.")

        return ref_id
