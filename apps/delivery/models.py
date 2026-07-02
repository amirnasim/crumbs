from decimal import Decimal

from django.db import models


class DeliveryZone(models.Model):
    class ZoneCode(models.TextChoices):
        TEHRAN = "tehran", "Tehran"
        TEHRAN_SUBURBS = "tehran_suburbs", "Tehran Suburbs"
        OTHER_CITIES = "other_cities", "Other Cities"

    code = models.SlugField(max_length=40, unique=True, choices=ZoneCode.choices)
    name = models.CharField(max_length=120)
    cities = models.JSONField(
        default=list,
        help_text="List of city names served (Persian or English, case-insensitive).",
    )
    states = models.JSONField(
        default=list,
        blank=True,
        help_text="Optional list of province/state names.",
    )
    delivery_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    express_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    min_order_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
    )
    free_delivery_threshold = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Subtotal above which standard courier delivery is free.",
    )
    is_active = models.BooleanField(default=True, db_index=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "منطقه ارسال"
        verbose_name_plural = "مناطق ارسال"

    def __str__(self):
        return self.name


class OrderStatusLog(models.Model):
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="status_logs",
    )
    from_status = models.CharField(max_length=30, blank=True)
    to_status = models.CharField(max_length=30)
    note = models.CharField(max_length=255, blank=True)
    actor = models.CharField(max_length=120, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "لاگ وضعیت سفارش"
        verbose_name_plural = "لاگ‌های وضعیت سفارش"

    def __str__(self):
        return f"{self.order.order_number}: {self.from_status} → {self.to_status}"
