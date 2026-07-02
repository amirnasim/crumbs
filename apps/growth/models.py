from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class AbandonedCartTracker(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        REMINDED = "reminded", "Reminded"
        RECOVERED = "recovered", "Recovered"
        EXPIRED = "expired", "Expired"

    cart = models.OneToOneField(
        "cart.Cart",
        on_delete=models.CASCADE,
        related_name="abandonment_tracker",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="abandoned_carts",
    )
    phone = models.CharField(max_length=20, blank=True, db_index=True)
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    item_count = models.PositiveIntegerField(default=0)
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    last_activity_at = models.DateTimeField(default=timezone.now, db_index=True)
    reminder_count = models.PositiveIntegerField(default=0)
    last_reminder_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        db_index=True,
    )
    recovered_order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="recovered_from_abandonment",
    )
    funnel_step = models.PositiveSmallIntegerField(default=0)
    offered_coupon = models.ForeignKey(
        "growth.Coupon",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="abandoned_cart_offers",
    )
    sms_conversion_tracked = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-last_activity_at"]
        verbose_name = "سبد رها شده"
        verbose_name_plural = "سبدهای رها شده"
        indexes = [
            models.Index(fields=["status", "last_activity_at"]),
            models.Index(fields=["phone", "status"]),
        ]

    def __str__(self):
        return f"Abandoned cart #{self.cart_id} ({self.status})"


class CustomerSegment(models.Model):
    class Code(models.TextChoices):
        NEW = "new", "New"
        ACTIVE = "active", "Active"
        VIP = "vip", "VIP"
        AT_RISK = "at_risk", "At Risk"
        DORMANT = "dormant", "Dormant"

    code = models.CharField(max_length=20, choices=Code.choices, unique=True)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["code"]
        verbose_name = "بخش مشتری"
        verbose_name_plural = "بخش‌های مشتری"

    def __str__(self):
        return self.name


class CustomerSegmentMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="segment_memberships",
    )
    segment = models.ForeignKey(
        CustomerSegment,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    assigned_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "عضویت بخش مشتری"
        verbose_name_plural = "عضویت‌های بخش مشتری"
        constraints = [
            models.UniqueConstraint(
                fields=["user", "segment"],
                name="unique_user_segment",
            ),
        ]

    def __str__(self):
        return f"{self.user} → {self.segment.code}"


class PromotionCampaign(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SENT = "sent", "Sent"

    name = models.CharField(max_length=120)
    message = models.TextField()
    segment = models.ForeignKey(
        CustomerSegment,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="campaigns",
    )
    status = models.CharField(max_length=10, choices=Status.choices, default=Status.DRAFT)
    sent_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "کمپین پروموشن"
        verbose_name_plural = "کمپین‌های پروموشن"

    def __str__(self):
        return self.name


from growth.models_revenue import (  # noqa: E402, F401
    Coupon,
    CouponRedemption,
    CustomerCLVProfile,
    DailyRevenueSnapshot,
    FunnelAnalyticsSnapshot,
    GrowthEvent,
    PromotionRule,
    Referral,
    ReferralCode,
    RevenueAttribution,
)
