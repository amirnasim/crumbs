from decimal import Decimal

from django.db import models


class Payment(models.Model):
    class Provider(models.TextChoices):
        ZARINPAL = "zarinpal", "Zarinpal"
        STRIPE = "stripe", "Stripe"
        COD = "cod", "Cash on Delivery"
        CASH = "cash", "Counter Cash"
        COUNTER_CARD = "counter_card", "Counter Card"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELLED = "cancelled", "Cancelled"
        REFUNDED = "refunded", "Refunded"

    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.PROTECT,
        related_name="payments",
    )
    provider = models.CharField(max_length=20, choices=Provider.choices, db_index=True)
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )
    amount = models.DecimalField("مبلغ", max_digits=10, decimal_places=2)
    currency = models.CharField("ارز", max_length=3, default="irr")
    provider_payment_id = models.CharField(max_length=255, blank=True, db_index=True)
    provider_checkout_session_id = models.CharField(max_length=255, blank=True, db_index=True)
    checkout_url = models.URLField(blank=True, max_length=500)
    failure_message = models.TextField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "پرداخت"
        verbose_name_plural = "پرداخت‌ها"
        indexes = [
            models.Index(fields=["order", "status"]),
            models.Index(fields=["provider", "status", "created_at"]),
        ]

    def __str__(self):
        return f"{self.provider} payment for {self.order.order_number}"

    @property
    def has_active_zarinpal_checkout(self) -> bool:
        return (
            self.provider == self.Provider.ZARINPAL
            and self.status == self.Status.PROCESSING
            and bool(self.provider_checkout_session_id)
            and bool(self.checkout_url)
        )


class PaymentEvent(models.Model):
    provider = models.CharField(max_length=20, choices=Payment.Provider.choices)
    event_id = models.CharField(max_length=255, unique=True, db_index=True)
    event_type = models.CharField(max_length=120, db_index=True)
    payload = models.JSONField()
    processed = models.BooleanField(default=False, db_index=True)
    processing_error = models.TextField(blank=True)
    processed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "رویداد پرداخت"
        verbose_name_plural = "رویدادهای پرداخت"

    def __str__(self):
        return f"{self.provider}:{self.event_type}:{self.event_id}"
