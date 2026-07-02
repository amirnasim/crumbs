class PaymentError(Exception):
    """Base exception for payment operations."""


class PaymentConfigurationError(PaymentError):
    """Raised when payment provider configuration is invalid."""


class PaymentProviderError(PaymentError):
    """Raised when the payment provider returns an error."""


class WebhookVerificationError(PaymentError):
    """Raised when webhook signature verification fails."""


class WebhookProcessingError(PaymentError):
    """Raised when webhook event processing fails."""


class PaymentAmountMismatchError(PaymentError):
    """Raised when payment amount does not match the order total."""
