import logging
import re

import requests
from django.conf import settings

from notifications.exceptions import SMSConfigurationError, SMSDeliveryError
from notifications.providers.base import SMSProvider, SMSResult

logger = logging.getLogger(__name__)


class KavenegarSMSProvider(SMSProvider):
    """Iran-focused SMS provider via Kavenegar API."""

    provider_name = "kavenegar"

    def __init__(self):
        self.api_key = settings.KAVENEGAR_API_KEY
        self.sender = settings.KAVENEGAR_SENDER
        if not self.api_key:
            raise SMSConfigurationError("KAVENEGAR_API_KEY is not configured.")

    def send(self, recipient: str, message: str) -> SMSResult:
        phone = normalize_iran_phone(recipient)
        url = f"https://api.kavenegar.com/v1/{self.api_key}/sms/send.json"
        payload = {
            "receptor": phone,
            "message": message,
        }
        if self.sender:
            payload["sender"] = self.sender

        try:
            response = requests.post(url, data=payload, timeout=15)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as exc:
            raise SMSDeliveryError(str(exc)) from exc

        entries = data.get("entries") or []
        if entries and entries[0].get("messageid"):
            return SMSResult(success=True, message_id=str(entries[0]["messageid"]))

        return SMSResult(success=False, error=str(data.get("return", {}).get("message", "Unknown error")))


def normalize_iran_phone(phone: str) -> str:
    digits = re.sub(r"\D", "", phone or "")
    if digits.startswith("98"):
        return digits
    if digits.startswith("0"):
        return "98" + digits[1:]
    if digits.startswith("9") and len(digits) == 10:
        return "98" + digits
    return digits
