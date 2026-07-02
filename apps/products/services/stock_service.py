"""Stock domain service — concurrency-safe reservations and capacity control."""

from inventory import services as _inventory


class StockService:
    check_availability = staticmethod(_inventory.check_cart_availability)
    get_available_quantity = staticmethod(_inventory.get_available_quantity)
    reserve_for_order = staticmethod(_inventory.reserve_for_order)
    confirm_reservations = staticmethod(_inventory.confirm_reservations)
    release_reservations = staticmethod(_inventory.release_reservations)
    fulfill_reservations = staticmethod(_inventory.fulfill_reservations)
    expire_stale_reservations = staticmethod(_inventory.expire_stale_reservations)
    reserve_for_cart_item = staticmethod(_inventory.reserve_for_cart_item)
    release_cart_reservations = staticmethod(_inventory.release_cart_reservations)
    release_cart_reservations_for_product = staticmethod(
        _inventory.release_cart_reservations_for_product
    )
