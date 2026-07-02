from datetime import date, timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from inventory.exceptions import CapacityExceededError, InsufficientStockError
from inventory.models import DailyProductionCapacity, ProductInventory, StockReservation
from products.models import Product


def get_or_create_inventory(product: Product) -> ProductInventory:
    inventory, _ = ProductInventory.objects.get_or_create(product=product)
    return inventory


def get_available_quantity(product: Product) -> int:
    inventory = get_or_create_inventory(product)
    return inventory.available_quantity


def check_cart_availability(product: Product, quantity: int) -> None:
    if not product.is_available:
        raise InsufficientStockError(f"{product.name} is not available.")

    inventory = get_or_create_inventory(product)
    if not inventory.track_stock:
        return

    if quantity > inventory.available_quantity:
        raise InsufficientStockError(
            f"Only {inventory.available_quantity} units of {product.name} are available."
        )


def _get_or_create_daily_capacity(product: Product, production_date: date) -> DailyProductionCapacity:
    capacity, _ = DailyProductionCapacity.objects.get_or_create(
        product=product,
        production_date=production_date,
        defaults={"max_units": _default_daily_capacity(product)},
    )
    return capacity


def _default_daily_capacity(product: Product) -> int:
    inventory = get_or_create_inventory(product)
    if inventory.track_stock:
        return max(inventory.stock_quantity, 50)
    return 100


def find_fulfillment_date(product: Product, quantity: int, *, start_date: date | None = None) -> date:
    inventory = get_or_create_inventory(product)
    current = start_date or timezone.localdate()
    max_days = 14

    for offset in range(max_days):
        target = current + timedelta(days=offset)
        capacity = _get_or_create_daily_capacity(product, target)
        if capacity.available_units >= quantity:
            return target
        if offset == 0 and inventory.track_stock and inventory.available_quantity >= quantity:
            return target

    if inventory.allow_preorder:
        raise CapacityExceededError(
            f"{product.name} is fully booked for the next {max_days} days. Please try a smaller quantity."
        )
    raise CapacityExceededError(f"{product.name} is not available for the requested quantity.")


def _reserve_item(
    order,
    product: Product,
    quantity: int,
    *,
    cart=None,
    hold_minutes: int = 120,
) -> StockReservation:
    inventory = ProductInventory.objects.select_for_update().get_or_create(product=product)[0]
    fulfillment_date = find_fulfillment_date(product, quantity)

    if inventory.track_stock and quantity > inventory.available_quantity:
        if inventory.allow_preorder:
            fulfillment_date = find_fulfillment_date(product, quantity, start_date=fulfillment_date)
        else:
            raise InsufficientStockError(
                f"Only {inventory.available_quantity} units of {product.name} are available."
            )

    capacity = DailyProductionCapacity.objects.select_for_update().get_or_create(
        product=product,
        production_date=fulfillment_date,
        defaults={"max_units": _default_daily_capacity(product)},
    )[0]

    if capacity.available_units < quantity:
        raise CapacityExceededError(
            f"Daily capacity for {product.name} on {fulfillment_date} is insufficient."
        )

    capacity.reserved_units = F("reserved_units") + quantity
    capacity.save(update_fields=["reserved_units"])
    capacity.refresh_from_db()

    if inventory.track_stock:
        inventory.reserved_quantity = F("reserved_quantity") + quantity
        inventory.save(update_fields=["reserved_quantity", "updated_at"])
        inventory.refresh_from_db()

    return StockReservation.objects.create(
        product=product,
        order=order,
        cart=cart,
        quantity=quantity,
        production_date=fulfillment_date,
        status=StockReservation.Status.ACTIVE,
        expires_at=timezone.now() + timedelta(minutes=hold_minutes),
    )


@transaction.atomic
def reserve_for_order(order) -> list[StockReservation]:
    reservations: list[StockReservation] = []
    items = list(order.items.select_related("product"))

    for item in items:
        reservation = _reserve_item(order, item.product, item.quantity, hold_minutes=120)
        reservations.append(reservation)
        item.fulfillment_date = reservation.production_date
        item.save(update_fields=["fulfillment_date"])

    dates = [reservation.production_date for reservation in reservations]
    order.fulfillment_date = max(dates) if dates else None
    order.save(update_fields=["fulfillment_date", "updated_at"])
    return reservations


@transaction.atomic
def release_cart_reservations(cart) -> int:
    """Release all ACTIVE reservations held by a cart. Idempotent."""
    reservations = StockReservation.objects.select_for_update().filter(
        cart=cart,
        status=StockReservation.Status.ACTIVE,
    )
    count = 0
    for reservation in reservations:
        _release_single_reservation(reservation)
        count += 1
    return count


@transaction.atomic
def release_cart_reservations_for_product(cart, product: Product) -> int:
    """Release ACTIVE cart reservations for one product. Idempotent."""
    reservations = StockReservation.objects.select_for_update().filter(
        cart=cart,
        product=product,
        status=StockReservation.Status.ACTIVE,
    )
    count = 0
    for reservation in reservations:
        _release_single_reservation(reservation)
        count += 1
    return count


@transaction.atomic
def reserve_for_cart_item(cart, product: Product, quantity: int) -> StockReservation | None:
    inventory = get_or_create_inventory(product)
    if not inventory.track_stock:
        return None

    minutes = settings.CART_RESERVATION_MINUTES
    for reservation in StockReservation.objects.select_for_update().filter(
        cart=cart,
        product=product,
        status=StockReservation.Status.ACTIVE,
    ):
        _release_single_reservation(reservation)

    return _reserve_item(None, product, quantity, cart=cart, hold_minutes=minutes)


@transaction.atomic
def confirm_reservations(order) -> None:
    reservations = StockReservation.objects.select_for_update().filter(
        order=order,
        status=StockReservation.Status.ACTIVE,
    )
    for reservation in reservations:
        reservation.status = StockReservation.Status.CONFIRMED
        reservation.expires_at = None
        reservation.save(update_fields=["status", "expires_at", "updated_at"])


@transaction.atomic
def release_reservations(order) -> None:
    reservations = StockReservation.objects.select_for_update().filter(
        order=order,
        status__in=[StockReservation.Status.ACTIVE, StockReservation.Status.CONFIRMED],
    )
    for reservation in reservations:
        _release_single_reservation(reservation)


def _release_single_reservation(reservation: StockReservation) -> None:
    if reservation.status in {StockReservation.Status.RELEASED, StockReservation.Status.EXPIRED}:
        return

    inventory = ProductInventory.objects.select_for_update().filter(product=reservation.product).first()
    capacity = DailyProductionCapacity.objects.select_for_update().filter(
        product=reservation.product,
        production_date=reservation.production_date,
    ).first()

    if reservation.status in {StockReservation.Status.CONFIRMED, StockReservation.Status.ACTIVE}:
        if inventory and inventory.track_stock:
            inventory.reserved_quantity = max(0, inventory.reserved_quantity - reservation.quantity)
            inventory.save(update_fields=["reserved_quantity", "updated_at"])
        if capacity:
            capacity.reserved_units = max(0, capacity.reserved_units - reservation.quantity)
            capacity.save(update_fields=["reserved_units"])

    reservation.status = StockReservation.Status.RELEASED
    reservation.save(update_fields=["status", "updated_at"])


@transaction.atomic
def fulfill_reservations(order) -> None:
    reservations = list(
        StockReservation.objects.select_for_update()
        .filter(
            order=order,
            status=StockReservation.Status.CONFIRMED,
        )
        .select_related("product")
    )
    if not reservations:
        return

    for reservation in reservations:
        inventory = ProductInventory.objects.select_for_update().get(product=reservation.product)
        capacity = DailyProductionCapacity.objects.select_for_update().get_or_create(
            product=reservation.product,
            production_date=reservation.production_date,
            defaults={"max_units": _default_daily_capacity(reservation.product)},
        )[0]

        if inventory.track_stock:
            inventory.stock_quantity = max(0, inventory.stock_quantity - reservation.quantity)
            inventory.reserved_quantity = max(0, inventory.reserved_quantity - reservation.quantity)
            inventory.save(update_fields=["stock_quantity", "reserved_quantity", "updated_at"])

        capacity.reserved_units = max(0, capacity.reserved_units - reservation.quantity)
        capacity.fulfilled_units += reservation.quantity
        capacity.save(update_fields=["fulfilled_units", "reserved_units"])

        reservation.status = StockReservation.Status.RELEASED
        reservation.save(update_fields=["status", "updated_at"])

        if inventory.track_stock and inventory.available_quantity == 0:
            reservation.product.availability_status = Product.AvailabilityStatus.OUT_OF_STOCK
            reservation.product.save(update_fields=["availability_status", "updated_at"])


@transaction.atomic
def expire_stale_reservations() -> int:
    now = timezone.now()
    expired = StockReservation.objects.select_for_update().filter(
        status=StockReservation.Status.ACTIVE,
        expires_at__lt=now,
    )
    count = 0
    for reservation in expired:
        _release_single_reservation(reservation)
        reservation.status = StockReservation.Status.EXPIRED
        reservation.save(update_fields=["status", "updated_at"])
        count += 1
    return count
