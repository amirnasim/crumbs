class OrderError(Exception):
    """Base exception for order operations."""


class EmptyCartError(OrderError):
    """Raised when checkout is attempted on an empty cart."""


class CheckoutError(OrderError):
    """Raised when checkout validation fails."""
