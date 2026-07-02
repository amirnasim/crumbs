from decimal import Decimal

from django.conf import settings
from django.db import models


class LoyaltyAccount(models.Model):
    class Tier(models.TextChoices):
        NORMAL = "normal", "Normal"
        SILVER = "silver", "Silver"
        GOLD = "gold", "Gold"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="loyalty",
    )
    points = models.PositiveIntegerField(default=0)
    lifetime_points = models.PositiveIntegerField(default=0)
    lifetime_spend = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    tier = models.CharField(
        max_length=10,
        choices=Tier.choices,
        default=Tier.NORMAL,
        db_index=True,
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-lifetime_points"]
        verbose_name = "حساب وفاداری"
        verbose_name_plural = "حساب‌های وفاداری"

    def __str__(self):
        return f"{self.user} — {self.tier} ({self.points} pts)"


class LoyaltyTransaction(models.Model):
    class Type(models.TextChoices):
        EARN = "earn", "Earn"
        REDEEM = "redeem", "Redeem"
        ADJUST = "adjust", "Adjust"

    account = models.ForeignKey(
        LoyaltyAccount,
        on_delete=models.CASCADE,
        related_name="transactions",
    )
    transaction_type = models.CharField(max_length=10, choices=Type.choices)
    points = models.IntegerField()
    balance_after = models.PositiveIntegerField()
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="loyalty_transactions",
    )
    description = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "تراکنش وفاداری"
        verbose_name_plural = "تراکنش‌های وفاداری"

    def __str__(self):
        return f"{self.account.user} {self.transaction_type} {self.points}"
