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


STOCK_CAPACITY_EXCEEDED_MESSAGE = "تعداد درخواستی بیشتر از موجودی قابل فروش است."
INVALID_QUANTITY_MESSAGE = "تعداد وارد شده معتبر نیست."


def cart_user_error_message(exc: Exception) -> str:
    from inventory.exceptions import CapacityExceededError, InsufficientStockError

    if isinstance(exc, (InsufficientStockError, CapacityExceededError)):
        return STOCK_CAPACITY_EXCEEDED_MESSAGE
    if isinstance(exc, ValueError):
        return INVALID_QUANTITY_MESSAGE
    return str(exc)
