"""Growth & revenue models — Milestone 11C."""

from decimal import Decimal

from django.conf import settings
from django.db import models
from django.utils import timezone


class Coupon(models.Model):
    class DiscountType(models.TextChoices):
        PERCENTAGE = "percentage", "Percentage"
        FIXED = "fixed", "Fixed Amount"

    class CampaignType(models.TextChoices):
        GENERAL = "general", "General"
        FIRST_ORDER = "first_order", "First Order"
        SEASONAL = "seasonal", "Seasonal"
        ABANDONED_CART = "abandoned_cart", "Abandoned Cart Recovery"

    code = models.CharField(max_length=32, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    discount_type = models.CharField(max_length=16, choices=DiscountType.choices)
    discount_value = models.DecimalField(max_digits=10, decimal_places=2)
    campaign_type = models.CharField(
        max_length=20,
        choices=CampaignType.choices,
        default=CampaignType.GENERAL,
    )
    min_order_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    max_discount_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    usage_limit_global = models.PositiveIntegerField(null=True, blank=True)
    usage_limit_per_user = models.PositiveIntegerField(default=1)
    usage_count = models.PositiveIntegerField(default=0)
    stackable = models.BooleanField(default=False)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "کوپن"
        verbose_name_plural = "کوپن‌ها"

    def __str__(self):
        return f"{self.code} ({self.name})"

    @property
    def is_valid_now(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        if self.usage_limit_global is not None and self.usage_count >= self.usage_limit_global:
            return False
        return True


class CouponRedemption(models.Model):
    coupon = models.ForeignKey(Coupon, on_delete=models.PROTECT, related_name="redemptions")
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="coupon_redemptions",
    )
    order = models.OneToOneField(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="coupon_redemption",
    )
    discount_amount = models.DecimalField(max_digits=10, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "استفاده از کوپن"
        verbose_name_plural = "استفاده‌های کوپن"

    def __str__(self):
        return f"{self.coupon.code} → {self.order.order_number}"


class ReferralCode(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_code",
    )
    code = models.CharField(max_length=16, unique=True, db_index=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "کد معرف"
        verbose_name_plural = "کدهای معرف"

    def __str__(self):
        return f"{self.code} ({self.user})"


class Referral(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"
        REWARDED = "rewarded", "Rewarded"

    referrer = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referrals_made",
    )
    referred_user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="referral_received",
    )
    referral_code = models.ForeignKey(ReferralCode, on_delete=models.PROTECT, related_name="referrals")
    first_order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="referral_conversions",
    )
    status = models.CharField(max_length=16, choices=Status.choices, default=Status.PENDING)
    referrer_reward_points = models.PositiveIntegerField(default=0)
    referred_discount_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    created_at = models.DateTimeField(auto_now_add=True)
    rewarded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "معرفی"
        verbose_name_plural = "معرفی‌ها"

    def __str__(self):
        return f"{self.referrer} → {self.referred_user}"


class PromotionRule(models.Model):
    class RuleType(models.TextChoices):
        WEEKEND_DISCOUNT = "weekend_discount", "Weekend Discount"
        VIP_DISCOUNT = "vip_discount", "VIP Discount"
        BUY_X_GET_Y = "buy_x_get_y", "Buy X Get Y"
        CATEGORY_DISCOUNT = "category_discount", "Category Discount"

    name = models.CharField(max_length=120)
    rule_type = models.CharField(max_length=32, choices=RuleType.choices)
    config = models.JSONField(default=dict, blank=True)
    priority = models.PositiveIntegerField(default=100)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["priority", "-created_at"]
        verbose_name = "قانون پروموشن"
        verbose_name_plural = "قوانین پروموشن"

    def __str__(self):
        return self.name

    @property
    def is_valid_now(self) -> bool:
        now = timezone.now()
        if not self.is_active:
            return False
        if self.valid_from and now < self.valid_from:
            return False
        if self.valid_until and now > self.valid_until:
            return False
        return True


class GrowthEvent(models.Model):
    class EventType(models.TextChoices):
        PRODUCT_VIEW = "product_view", "Product View"
        ADD_TO_CART = "add_to_cart", "Add to Cart"
        CHECKOUT_START = "checkout_start", "Checkout Start"
        CHECKOUT_COMPLETE = "checkout_complete", "Checkout Complete"
        SMS_SENT = "sms_sent", "SMS Sent"
        SMS_CONVERSION = "sms_conversion", "SMS Conversion"

    event_type = models.CharField(max_length=32, choices=EventType.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="growth_events",
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    product = models.ForeignKey(
        "products.Product",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="growth_events",
    )
    cart = models.ForeignKey(
        "cart.Cart",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="growth_events",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="growth_events",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "رویداد رشد"
        verbose_name_plural = "رویدادهای رشد"
        indexes = [
            models.Index(fields=["event_type", "created_at"]),
        ]


class CustomerCLVProfile(models.Model):
    class RevenueTier(models.TextChoices):
        LOW = "low", "Low Value"
        MEDIUM = "medium", "Medium Value"
        HIGH = "high", "High Value (VIP)"

    class FrequencyTag(models.TextChoices):
        NEW = "new", "New"
        OCCASIONAL = "occasional", "Occasional"
        REGULAR = "regular", "Regular"
        LOYAL = "loyal", "Loyal"

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="clv_profile",
    )
    lifetime_revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    order_count = models.PositiveIntegerField(default=0)
    avg_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0.00"))
    clv_score = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0.00"))
    revenue_tier = models.CharField(
        max_length=16,
        choices=RevenueTier.choices,
        default=RevenueTier.LOW,
        db_index=True,
    )
    frequency_tag = models.CharField(
        max_length=16,
        choices=FrequencyTag.choices,
        default=FrequencyTag.NEW,
    )
    last_order_at = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "پروفایل ارزش مشتری"
        verbose_name_plural = "پروفایل‌های ارزش مشتری"

    def __str__(self):
        return f"CLV {self.user} ({self.revenue_tier})"


class RevenueAttribution(models.Model):
    class SourceType(models.TextChoices):
        SMS = "sms", "SMS"
        COUPON = "coupon", "Coupon"
        REFERRAL = "referral", "Referral"
        PROMOTION = "promotion", "Promotion Rule"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="revenue_attributions",
    )
    source_type = models.CharField(max_length=16, choices=SourceType.choices, db_index=True)
    source_id = models.CharField(max_length=64, blank=True)
    source_label = models.CharField(max_length=255, blank=True)
    attributed_amount = models.DecimalField(max_digits=10, decimal_places=2)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "انتساب درآمد"
        verbose_name_plural = "انتساب‌های درآمد"
        indexes = [
            models.Index(fields=["source_type", "created_at"]),
        ]


class DailyRevenueSnapshot(models.Model):
    report_date = models.DateField(unique=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-report_date"]
        verbose_name = "تصویر درآمد روزانه"
        verbose_name_plural = "تصاویر درآمد روزانه"


class FunnelAnalyticsSnapshot(models.Model):
    report_date = models.DateField(unique=True)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-report_date"]
        verbose_name = "تصویر قیف فروش"
        verbose_name_plural = "تصاویر قیف فروش"
