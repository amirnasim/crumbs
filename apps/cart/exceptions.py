class CartError(Exception):
    """Base exception for cart operations."""


class ProductUnavailableError(CartError):
    """Raised when a product cannot be added to the cart."""


class InvalidQuantityError(CartError):
    """Raised when quantity is invalid."""


class CheckoutAlreadyInProgress(CartError):
    """Raised when checkout is already running for this cart."""


class CartMutationBlocked(CartError):
    """Raised when the cart is locked during an active checkout."""
