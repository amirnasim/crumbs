from django.db import models
from django.utils import timezone


class ProductInventory(models.Model):
    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="inventory",
    )
    track_stock = models.BooleanField(default=True)
    stock_quantity = models.PositiveIntegerField(default=0)
    reserved_quantity = models.PositiveIntegerField(default=0)
    low_stock_threshold = models.PositiveIntegerField(default=5)
    allow_preorder = models.BooleanField(
        default=True,
        help_text="Allow booking beyond today's capacity on future production days.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "موجودی محصول"
        verbose_name_plural = "موجودی محصولات"

    def __str__(self):
        return f"Inventory for {self.product.name}"

    @property
    def available_quantity(self) -> int:
        if not self.track_stock:
            return 999_999
        return max(0, self.stock_quantity - self.reserved_quantity)


class DailyProductionCapacity(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="daily_capacities",
    )
    production_date = models.DateField(db_index=True)
    max_units = models.PositiveIntegerField()
    reserved_units = models.PositiveIntegerField(default=0)
    fulfilled_units = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["production_date"]
        verbose_name = "ظرفیت تولید روزانه"
        verbose_name_plural = "ظرفیت‌های تولید روزانه"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "production_date"],
                name="unique_daily_capacity_per_product",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "production_date"]),
        ]

    def __str__(self):
        return f"{self.product.name} — {self.production_date} ({self.max_units})"

    @property
    def available_units(self) -> int:
        return max(0, self.max_units - self.reserved_units - self.fulfilled_units)


class StockReservation(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        CONFIRMED = "confirmed", "Confirmed"
        RELEASED = "released", "Released"
        EXPIRED = "expired", "Expired"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )
    cart = models.ForeignKey(
        "cart.Cart",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="stock_reservations",
    )
    quantity = models.PositiveIntegerField()
    production_date = models.DateField(db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    expires_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "رزرو موجودی"
        verbose_name_plural = "رزروهای موجودی"
        indexes = [
            models.Index(fields=["status", "production_date"]),
            models.Index(fields=["order", "status"]),
        ]

    def __str__(self):
        return f"{self.quantity} x {self.product.name} ({self.status})"
