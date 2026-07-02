class FulfillmentError(Exception):
    """Base fulfillment error."""


class InvalidTransitionError(FulfillmentError):
    """Order status transition is not allowed."""


class UndeliverableAddressError(FulfillmentError):
    """Address is outside active delivery zones."""


class MinimumOrderError(FulfillmentError):
    """Order subtotal is below zone minimum."""
