import logging

from notifications.providers.base import SMSProvider, SMSResult

logger = logging.getLogger(__name__)


class ConsoleSMSProvider(SMSProvider):
    """Development provider — logs SMS without sending."""

    provider_name = "console"

    def send(self, recipient: str, message: str) -> SMSResult:
        logger.info("SMS to %s: %s", recipient, message)
        return SMSResult(success=True, message_id="console-dev")
