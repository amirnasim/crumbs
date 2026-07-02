from cart.models import Cart
from cart.services import get_or_create_cart, merge_carts

from .models import Address, CustomerProfile


def resolve_login_identifier(identifier: str) -> str:
    """Map a phone number to username when profile phone matches.

    Password authentication still uses Django's username field internally.
    TODO: Replace with SMS OTP login when provider-backed auth is implemented.
    """
    normalized = (identifier or "").strip()
    if not normalized:
        return normalized

    profile = (
        CustomerProfile.objects.select_related("user")
        .filter(phone=normalized)
        .first()
    )
    if profile:
        return profile.user.get_username()

    return normalized


def merge_session_cart_on_login(request, user) -> None:
    """Merge anonymous session cart into the authenticated user's cart."""
    session_key = request.session.session_key
    if not session_key:
        return

    session_cart = Cart.objects.filter(session_key=session_key).first()
    if session_cart is None:
        return

    user_cart, _ = get_or_create_cart(user=user)
    merge_carts(session_cart, user_cart)


def get_default_address(user) -> Address | None:
    return user.addresses.filter(is_default=True).first() or user.addresses.first()


def get_checkout_initial(user) -> dict:
    """Build cafe checkout form initial data from user profile."""
    return {
        "email": user.email,
        "first_name": user.first_name,
        "last_name": user.last_name,
        "phone": getattr(getattr(user, "profile", None), "phone", ""),
    }
