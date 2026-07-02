"""SMS provider mocks."""

from notifications.providers.base import SMSProvider, SMSResult


class RecordingSMSProvider(SMSProvider):
    """Captures all SMS sends for assertions."""

    provider_name = "recording"

    def __init__(self):
        self.messages: list[tuple[str, str]] = []

    def send(self, recipient: str, message: str) -> SMSResult:
        self.messages.append((recipient, message))
        return SMSResult(success=True, message_id=f"sms-{len(self.messages)}")
