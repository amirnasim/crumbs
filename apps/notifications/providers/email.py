import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass

from django.conf import settings
from django.core.mail import send_mail

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class EmailResult:
    success: bool
    error: str = ""


class EmailProvider(ABC):
    provider_name: str

    @abstractmethod
    def send(self, *, to: str, subject: str, body: str) -> EmailResult:
        raise NotImplementedError


class DjangoEmailProvider(EmailProvider):
    """Send email through Django's configured EMAIL_BACKEND."""

    provider_name = "django"

    def send(self, *, to: str, subject: str, body: str) -> EmailResult:
        if not to:
            return EmailResult(success=False, error="Missing recipient email.")

        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[to],
            fail_silently=False,
        )
        return EmailResult(success=True)


class ConsoleEmailProvider(EmailProvider):
    """Development provider — logs email without sending."""

    provider_name = "console"

    def send(self, *, to: str, subject: str, body: str) -> EmailResult:
        logger.info("Email to %s | subject=%s | body=%s", to, subject, body)
        return EmailResult(success=True)
