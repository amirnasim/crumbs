import json
import logging

from django.contrib.admin.views.decorators import staff_member_required
from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST

from core.observability import log_payment_event
from payments.exceptions import (
    PaymentConfigurationError,
    PaymentError,
    WebhookProcessingError,
    WebhookVerificationError,
)
from payments.models import Payment
from payments.services import handle_stripe_webhook, handle_zarinpal_callback, initiate_payment

logger = logging.getLogger(__name__)


@csrf_exempt
@require_POST
def stripe_webhook(request):
    payload = request.body
    signature = request.META.get("HTTP_STRIPE_SIGNATURE", "")

    try:
        handle_stripe_webhook(payload, signature)
    except WebhookVerificationError:
        logger.warning("Rejected Stripe webhook with invalid signature.")
        return HttpResponse(status=400)
    except PaymentConfigurationError:
        logger.error("Stripe webhook rejected due to missing configuration.")
        return HttpResponse(status=503)
    except WebhookProcessingError:
        return HttpResponse(status=500)

    return HttpResponse(status=200)


@csrf_exempt
@require_GET
def zarinpal_callback(request):
    authority = request.GET.get("Authority") or request.GET.get("authority", "")
    status = request.GET.get("Status") or request.GET.get("status", "")

    if not authority:
        return JsonResponse({"error": "Missing Zarinpal authority."}, status=400)

    payment = Payment.objects.filter(
        provider=Payment.Provider.ZARINPAL,
        provider_checkout_session_id=authority,
    ).first()

    payload = json.dumps(
        {
            "authority": authority,
            "status": status,
            "payment_id": payment.pk if payment else None,
        }
    ).encode("utf-8")

    try:
        event = handle_zarinpal_callback(payload)
    except WebhookVerificationError as exc:
        logger.warning("Rejected Zarinpal callback")
        log_payment_event(
            "payment_callback_rejected",
            provider=Payment.Provider.ZARINPAL,
            status="verification_error",
            request_path=request.path,
        )
        return JsonResponse({"error": str(exc)}, status=400)
    except PaymentConfigurationError as exc:
        logger.error("Zarinpal callback rejected due to configuration")
        log_payment_event(
            "payment_callback_rejected",
            provider=Payment.Provider.ZARINPAL,
            status="configuration_error",
            request_path=request.path,
        )
        return JsonResponse({"error": str(exc)}, status=503)
    except WebhookProcessingError as exc:
        logger.exception("Zarinpal callback processing failed")
        log_payment_event(
            "payment_callback_failed",
            provider=Payment.Provider.ZARINPAL,
            status="processing_error",
            request_path=request.path,
        )
        return JsonResponse({"error": str(exc)}, status=500)

    if payment:
        log_payment_event(
            "payment_callback_received",
            payment_id=payment.pk,
            order_id=payment.order_id,
            provider=Payment.Provider.ZARINPAL,
            status=status or "unknown",
            request_path=request.path,
        )

    return JsonResponse(
        {
            "status": "ok",
            "processed": event.processed,
            "event_id": event.event_id,
        }
    )


@staff_member_required
@require_POST
def create_checkout_session(request, order_number):
    """
    Backend endpoint to initiate Stripe Checkout without a storefront UI.
    Intended for admin/testing workflows until Milestone 6 frontend.
    """
    from orders.models import Order
    from payments.exceptions import PaymentError

    try:
        order = Order.objects.get(order_number=order_number)
        payment = initiate_payment(order)
    except Order.DoesNotExist:
        return JsonResponse({"error": "Order not found."}, status=404)
    except PaymentError as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except PaymentConfigurationError as exc:
        return JsonResponse({"error": str(exc)}, status=503)

    return JsonResponse(
        {
            "order_number": order.order_number,
            "payment_id": payment.pk,
            "checkout_url": payment.checkout_url,
            "status": payment.status,
        }
    )
