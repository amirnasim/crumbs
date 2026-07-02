from decimal import Decimal

from django.conf import settings
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce


class Cart(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="cart",
    )
    session_key = models.CharField(
        max_length=40,
        null=True,
        blank=True,
        unique=True,
        db_index=True,
    )
    applied_coupon_code = models.CharField(max_length=32, blank=True, db_index=True)
    referral_code = models.CharField(max_length=16, blank=True, db_index=True)
    active_checkout_order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="checkout_source_cart",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "سبد خرید"
        verbose_name_plural = "سبدهای خرید"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(user__isnull=False) | models.Q(session_key__isnull=False),
                name="cart_requires_user_or_session",
            ),
        ]

    def __str__(self):
        if self.user_id:
            return f"Cart (user: {self.user})"
        return f"Cart (session: {self.session_key})"

    @property
    def total_items(self) -> int:
        aggregate = self.items.aggregate(total=Coalesce(Sum("quantity"), 0))
        return aggregate["total"]

    @property
    def is_empty(self) -> bool:
        return self.total_items == 0

    def get_subtotal(self) -> Decimal:
        total = Decimal("0.00")
        for item in self.items.select_related("product"):
            total += item.line_total
        return total


class CartItem(models.Model):
    cart = models.ForeignKey(
        Cart,
        on_delete=models.CASCADE,
        related_name="items",
    )
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="cart_items",
    )
    quantity = models.PositiveIntegerField(default=1)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "قلم سبد"
        verbose_name_plural = "اقلام سبد"
        constraints = [
            models.UniqueConstraint(
                fields=["cart", "product"],
                name="unique_product_per_cart",
            ),
            models.CheckConstraint(
                condition=models.Q(quantity__gte=1),
                name="cart_item_quantity_positive",
            ),
        ]
        ordering = ["created_at"]

    def __str__(self):
        return f"{self.quantity} x {self.product.name}"

    @property
    def line_total(self) -> Decimal:
        return self.product.price * self.quantity
