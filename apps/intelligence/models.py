"""Intelligence layer models — Milestone 12."""

from decimal import Decimal

from django.conf import settings
from django.db import models


class ProductIntelligenceMeta(models.Model):
    """Per-product intelligence weights (margin proxy, category role)."""

    product = models.OneToOneField(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="intelligence_meta",
    )
    margin_boost = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=Decimal("1.00"),
        help_text="Ranking multiplier for high-margin boosting (1.0 = neutral).",
    )
    is_cookie = models.BooleanField(default=False)
    is_coffee = models.BooleanField(default=False)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "متای هوش محصول"
        verbose_name_plural = "متاهای هوش محصول"

    def __str__(self):
        return f"Intel meta: {self.product.name}"


class ProductCoPurchase(models.Model):
    """Frequently bought together pairs."""

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="co_purchase_from",
    )
    related_product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="co_purchase_to",
    )
    co_count = models.PositiveIntegerField(default=0)
    affinity_score = models.DecimalField(max_digits=10, decimal_places=4, default=Decimal("0"))
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "خرید همزمان"
        verbose_name_plural = "خریدهای همزمان"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "related_product"],
                name="unique_co_purchase_pair",
            ),
        ]
        indexes = [
            models.Index(fields=["product", "-affinity_score"]),
        ]

    def __str__(self):
        return f"{self.product.name} + {self.related_product.name}"


class ProductDailyStats(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="daily_stats",
    )
    stat_date = models.DateField(db_index=True)
    units_sold = models.PositiveIntegerField(default=0)
    revenue = models.DecimalField(max_digits=12, decimal_places=2, default=Decimal("0"))
    order_count = models.PositiveIntegerField(default=0)
    peak_hour = models.PositiveSmallIntegerField(null=True, blank=True)
    weekday = models.PositiveSmallIntegerField(null=True, blank=True)
    hourly_distribution = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "آمار روزانه محصول"
        verbose_name_plural = "آمار روزانه محصولات"
        constraints = [
            models.UniqueConstraint(fields=["product", "stat_date"], name="unique_product_daily_stat"),
        ]
        ordering = ["-stat_date"]


class ProductDemandForecast(models.Model):
    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="demand_forecasts",
    )
    forecast_for_date = models.DateField(db_index=True)
    window_days = models.PositiveSmallIntegerField(default=7)
    predicted_units = models.DecimalField(max_digits=10, decimal_places=2)
    historical_avg = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    weekday_factor = models.DecimalField(max_digits=6, decimal_places=4, default=Decimal("1"))
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "پیش‌بینی تقاضا"
        verbose_name_plural = "پیش‌بینی‌های تقاضا"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "forecast_for_date", "window_days"],
                name="unique_product_forecast",
            ),
        ]
        ordering = ["-forecast_for_date"]


class ProductBakeRecommendation(models.Model):
    class Status(models.TextChoices):
        OK = "ok", "OK"
        LOW_STOCK = "low_stock", "Low Stock Warning"
        OVERSTOCK_RISK = "overstock_risk", "Overstock Risk"

    product = models.ForeignKey(
        "products.Product",
        on_delete=models.CASCADE,
        related_name="bake_recommendations",
    )
    recommendation_date = models.DateField(db_index=True)
    suggested_bake_qty = models.PositiveIntegerField(default=0)
    forecast_demand = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal("0"))
    current_stock = models.PositiveIntegerField(default=0)
    capacity_available = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.OK)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "توصیه پخت"
        verbose_name_plural = "توصیه‌های پخت"
        constraints = [
            models.UniqueConstraint(
                fields=["product", "recommendation_date"],
                name="unique_bake_recommendation_per_day",
            ),
        ]
        ordering = ["-recommendation_date"]


class CustomerIntelligenceProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="intelligence_profile",
    )
    behavioral_tags = models.JSONField(default=list, blank=True)
    engagement_score = models.PositiveIntegerField(default=0)
    category_affinity = models.JSONField(default=dict, blank=True)
    discount_sensitivity = models.DecimalField(max_digits=5, decimal_places=2, default=Decimal("0"))
    preferred_product_ids = models.JSONField(default=list, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "پروفایل هوش مشتری"
        verbose_name_plural = "پروفایل‌های هوش مشتری"

    def __str__(self):
        return f"Intel: {self.user} (score={self.engagement_score})"


class IntelligenceSnapshot(models.Model):
    class Period(models.TextChoices):
        DAILY = "daily", "Daily"
        WEEKLY = "weekly", "Weekly"

    report_date = models.DateField(db_index=True)
    period = models.CharField(max_length=10, choices=Period.choices, default=Period.DAILY)
    payload = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "تصویر هوش تجاری"
        verbose_name_plural = "تصاویر هوش تجاری"
        constraints = [
            models.UniqueConstraint(
                fields=["report_date", "period"],
                name="unique_intelligence_snapshot",
            ),
        ]
        ordering = ["-report_date"]


class UpsellImpression(models.Model):
    """Tracks upsell/recommendation slot impressions for effectiveness metrics."""

    class Slot(models.TextChoices):
        HOME = "home", "Home"
        PRODUCT = "product", "Product Detail"
        CART = "cart", "Cart"
        CHECKOUT = "checkout", "Checkout"
        SMS = "sms", "SMS Personalization"

    slot = models.CharField(max_length=20, choices=Slot.choices, db_index=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    session_key = models.CharField(max_length=40, blank=True, db_index=True)
    product_ids = models.JSONField(default=list)
    converted = models.BooleanField(default=False)
    conversion_order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "نمایش پیشنهاد فروش"
        verbose_name_plural = "نمایش‌های پیشنهاد فروش"
