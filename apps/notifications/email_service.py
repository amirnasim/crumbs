import logging

from django.conf import settings

from notifications.providers.email import ConsoleEmailProvider, DjangoEmailProvider, EmailProvider

logger = logging.getLogger(__name__)

ORDER_EMAIL_TEMPLATES = {
    "order_created": (
        "CRUMBS — Order {order_number} received",
        "Hello {name},\n\nYour order {order_number} was created.\nTotal: {total} IRR\n\nThank you for ordering from CRUMBS.",
    ),
    "payment_success": (
        "CRUMBS — Payment received for {order_number}",
        "Hello {name},\n\nWe received payment for order {order_number}.\nTotal: {total} IRR\n\nThank you.",
    ),
    "order_confirmed_by_shop": (
        "CRUMBS — Order {order_number} confirmed",
        "Hello {name},\n\nYour order {order_number} was confirmed by the shop.",
    ),
    "order_preparing": (
        "CRUMBS — Order {order_number} is being prepared",
        "Hello {name},\n\nYour order {order_number} is now being prepared.",
    ),
    "order_packaged": (
        "CRUMBS — Order {order_number} packaged",
        "Hello {name},\n\nYour order {order_number} has been packaged.",
    ),
    "order_out_for_delivery": (
        "CRUMBS — Order {order_number} is out for delivery",
        "Hello {name},\n\nYour order {order_number} is on its way.",
    ),
    "delivered": (
        "CRUMBS — Order {order_number} delivered",
        "Hello {name},\n\nYour order {order_number} was delivered. Enjoy!",
    ),
}


def get_email_provider() -> EmailProvider:
    provider = getattr(settings, "NOTIFICATIONS_EMAIL_PROVIDER", "django")
    if provider == "console":
        return ConsoleEmailProvider()
    return DjangoEmailProvider()


def render_email_template(template: str, context: dict) -> str:
    class SafeFormatDict(dict):
        def __missing__(self, key):
            return "{" + key + "}"

    return template.format_map(SafeFormatDict(context))


class EmailService:
    """Order notification emails via Django mail backends."""

    @staticmethod
    def send_order_event(
        event_code: str,
        recipient: str,
        context: dict,
    ) -> bool:
        if not getattr(settings, "NOTIFICATIONS_EMAIL_ENABLED", True):
            logger.info("Email notifications disabled; skipping %s", event_code)
            return False

        if not recipient:
            logger.info("No email recipient for event %s", event_code)
            return False

        templates = ORDER_EMAIL_TEMPLATES.get(event_code)
        if templates is None:
            logger.info("No email template configured for event %s", event_code)
            return False

        subject_template, body_template = templates
        subject = render_email_template(subject_template, context)
        body = render_email_template(body_template, context)
        provider = get_email_provider()
        result = provider.send(to=recipient, subject=subject, body=body)
        if not result.success:
            raise RuntimeError(result.error or "Email delivery failed.")
        return True
