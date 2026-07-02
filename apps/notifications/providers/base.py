from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class SMSResult:
    success: bool
    message_id: str = ""
    error: str = ""


class SMSProvider(ABC):
    provider_name: str

    @abstractmethod
    def send(self, recipient: str, message: str) -> SMSResult:
        raise NotImplementedError
