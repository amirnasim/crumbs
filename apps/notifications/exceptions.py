class SMSError(Exception):
    """Base exception for SMS operations."""


class SMSConfigurationError(SMSError):
    """Raised when SMS provider configuration is invalid."""


class SMSDeliveryError(SMSError):
    """Raised when SMS delivery fails."""
