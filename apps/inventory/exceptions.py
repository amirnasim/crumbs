class InventoryError(Exception):
    """Base inventory error."""


class InsufficientStockError(InventoryError):
    """Not enough stock to fulfill the request."""


class CapacityExceededError(InventoryError):
    """Daily production capacity exceeded for the requested date."""


class ReservationError(InventoryError):
    """Stock reservation could not be completed."""
