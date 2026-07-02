import logging

from notifications.email_service import EmailService
from notifications.services import SMSService

logger = logging.getLogger(__name__)


class NotificationService:
    """Unified order notification facade (SMS + email). Never raises to callers."""

    @staticmethod
    def notify_order_event(
        event_code: str,
        *,
        order,
        context: dict,
        phone: str = "",
    ) -> dict:
        """
        Deliver SMS and email for an order lifecycle event.
        Failures are logged; business flow must continue regardless.
        """
        result = {
            "event_code": event_code,
            "sms_log_id": None,
            "email_sent": False,
            "errors": [],
        }

        if phone:
            try:
                sms_log = SMSService.send_event(
                    event_code,
                    phone,
                    context,
                    user=getattr(order, "user", None),
                    order=order,
                )
                if sms_log is not None:
                    result["sms_log_id"] = sms_log.pk
            except Exception as exc:
                logger.exception(
                    "SMS notification failed for order %s event %s",
                    getattr(order, "order_number", order.pk),
                    event_code,
                )
                result["errors"].append(f"sms:{exc}")

        if getattr(order, "email", ""):
            try:
                result["email_sent"] = EmailService.send_order_event(
                    event_code,
                    order.email,
                    context,
                )
            except Exception as exc:
                logger.exception(
                    "Email notification failed for order %s event %s",
                    getattr(order, "order_number", order.pk),
                    event_code,
                )
                result["errors"].append(f"email:{exc}")

        return result

    @staticmethod
    def notify_order_created(order, *, phone: str, context: dict) -> dict:
        return NotificationService.notify_order_event(
            "order_created",
            order=order,
            context=context,
            phone=phone,
        )

    @staticmethod
    def notify_order_status_updated(order, *, phone: str, context: dict, event_code: str) -> dict:
        return NotificationService.notify_order_event(
            event_code,
            order=order,
            context=context,
            phone=phone,
        )

    @staticmethod
    def notify_payment_received(order, *, phone: str, context: dict) -> dict:
        return NotificationService.notify_order_event(
            "payment_success",
            order=order,
            context=context,
            phone=phone,
        )
