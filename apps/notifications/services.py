import logging

from django.conf import settings
from django.template import Context, Template

from notifications.exceptions import SMSConfigurationError
from notifications.models import SMSLog, SMSTemplate
from notifications.policies import apply_sms_policies
from notifications.providers.base import SMSProvider

logger = logging.getLogger(__name__)


def get_sms_provider() -> SMSProvider:
    provider = settings.SMS_PROVIDER
    if provider == "kavenegar":
        from notifications.providers.kavenegar import KavenegarSMSProvider

        return KavenegarSMSProvider()
    if provider == "console":
        from notifications.providers.console import ConsoleSMSProvider

        return ConsoleSMSProvider()
    raise SMSConfigurationError(f"Unsupported SMS provider: {provider}")


def render_template(body: str, context: dict) -> str:
    return Template(body).render(Context(context))


class SMSService:
    """Notification service for Iran-market SMS events."""

    ORDER_EVENTS = {
        "order_created",
        "payment_success",
        "payment_failed",
        "order_confirmed_by_shop",
        "order_preparing",
        "order_out_for_delivery",
        "delivered",
        "order_cancelled",
        "refund_processed",
        "abandoned_cart",
        "cod_reminder",
    }

    @staticmethod
    def send(
        recipient: str,
        message: str,
        *,
        template_code: str = "",
        user=None,
        order=None,
        metadata: dict | None = None,
        force: bool = False,
        dedupe_key: str | None = None,
    ) -> SMSLog:
        return send_sms(
            recipient,
            message,
            template_code=template_code,
            user=user,
            order=order,
            metadata=metadata,
            force=force,
            dedupe_key=dedupe_key,
        )

    @staticmethod
    def send_event(
        event_code: str,
        recipient: str,
        context: dict,
        *,
        user=None,
        order=None,
        metadata: dict | None = None,
        force: bool = False,
    ) -> SMSLog | None:
        """Synchronous send — intended for Celery workers only."""
        dedupe_key = f"{order.pk}:{event_code}" if order else f"{recipient}:{event_code}"
        return send_template_sms(
            event_code,
            recipient,
            context,
            user=user,
            order=order,
            metadata=metadata,
            force=force,
            dedupe_key=dedupe_key,
        )

    @staticmethod
    def enqueue_event(
        event_code: str,
        recipient: str,
        context: dict,
        *,
        user=None,
        order=None,
        dedupe_key: str | None = None,
    ):
        """Queue SMS event for async delivery."""
        from notifications.dispatch import dispatch_sms_event

        return dispatch_sms_event(
            event_code,
            recipient,
            context,
            user=user,
            order=order,
            dedupe_key=dedupe_key,
        )

    @staticmethod
    def retry_failed(*, max_attempts: int = 3) -> int:
        retried = 0
        logs = SMSLog.objects.filter(status=SMSLog.Status.FAILED).order_by("created_at")[:100]
        for log in logs:
            attempts = log.metadata.get("retry_count", 0)
            if attempts >= max_attempts:
                continue
            result = send_sms(
                log.recipient,
                log.message,
                template_code=log.template_code,
                user=log.user,
                order=log.order,
                metadata={**log.metadata, "retry_count": attempts + 1, "retry_of": log.pk},
                force=True,
            )
            if result.status == SMSLog.Status.SENT:
                retried += 1
        return retried


def send_sms(
    recipient: str,
    message: str,
    *,
    template_code: str = "",
    user=None,
    order=None,
    metadata: dict | None = None,
    force: bool = False,
    dedupe_key: str | None = None,
) -> SMSLog:
    metadata = dict(metadata or {})
    if dedupe_key:
        metadata["dedupe_key"] = dedupe_key
    elif order and template_code and "dedupe_key" not in metadata:
        metadata["dedupe_key"] = f"{order.pk}:{template_code}"

    if not recipient:
        return SMSLog.objects.create(
            provider=settings.SMS_PROVIDER,
            template_code=template_code,
            recipient="",
            message=message,
            status=SMSLog.Status.SKIPPED,
            error_message="Missing phone number.",
            user=user,
            order=order,
            metadata=metadata,
        )

    should_send, skip_reason = apply_sms_policies(
        recipient=recipient,
        template_code=template_code,
        order=order,
        metadata=metadata,
        force=force,
        dedupe_key=dedupe_key,
        user=user,
    )
    if not should_send:
        return SMSLog.objects.create(
            provider=settings.SMS_PROVIDER,
            template_code=template_code,
            recipient=recipient,
            message=message,
            status=SMSLog.Status.SKIPPED,
            error_message=skip_reason,
            user=user,
            order=order,
            metadata=metadata,
        )

    log = SMSLog.objects.create(
        provider=settings.SMS_PROVIDER,
        template_code=template_code,
        recipient=recipient,
        message=message,
        status=SMSLog.Status.PENDING,
        user=user,
        order=order,
        metadata=metadata,
    )

    if not settings.SMS_ENABLED:
        log.status = SMSLog.Status.SKIPPED
        log.error_message = "SMS_ENABLED is False."
        log.save(update_fields=["status", "error_message"])
        return log

    try:
        provider = get_sms_provider()
        result = provider.send(recipient, message)
    except Exception as exc:
        logger.exception("SMS delivery failed for %s", recipient)
        log.status = SMSLog.Status.FAILED
        log.error_message = str(exc)
        log.save(update_fields=["status", "error_message"])
        return log

    if result.success:
        log.status = SMSLog.Status.SENT
        log.provider_message_id = result.message_id
        log.save(update_fields=["status", "provider_message_id"])
    else:
        log.status = SMSLog.Status.FAILED
        log.error_message = result.error
        log.save(update_fields=["status", "error_message"])

    return log


def send_template_sms(
    template_code: str,
    recipient: str,
    context: dict,
    *,
    user=None,
    order=None,
    metadata: dict | None = None,
    force: bool = False,
    dedupe_key: str | None = None,
) -> SMSLog | None:
    try:
        template = SMSTemplate.objects.get(code=template_code, is_active=True)
    except SMSTemplate.DoesNotExist:
        logger.warning("SMS template not found: %s", template_code)
        return None

    message = render_template(template.body, context)
    return send_sms(
        recipient,
        message,
        template_code=template_code,
        user=user,
        order=order,
        metadata=metadata,
        force=force,
        dedupe_key=dedupe_key,
    )
