from django.conf import settings
from django.db import models


class SMSTemplate(models.Model):
    class Category(models.TextChoices):
        ORDER = "order", "Order"
        PAYMENT = "payment", "Payment"
        MARKETING = "marketing", "Marketing"
        ABANDONED_CART = "abandoned_cart", "Abandoned Cart"

    code = models.CharField(max_length=50, unique=True, db_index=True)
    name = models.CharField(max_length=120)
    category = models.CharField(max_length=20, choices=Category.choices, db_index=True)
    body = models.TextField(help_text="Use {placeholders} for dynamic values.")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["category", "code"]
        verbose_name = "قالب پیامک"
        verbose_name_plural = "قالب‌های پیامک"

    def __str__(self):
        return f"{self.code} ({self.name})"


class SMSLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"
        SKIPPED = "skipped", "Skipped"

    provider = models.CharField(max_length=30, db_index=True)
    template_code = models.CharField(max_length=50, blank=True, db_index=True)
    recipient = models.CharField(max_length=20, db_index=True)
    message = models.TextField()
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    provider_message_id = models.CharField(max_length=120, blank=True)
    error_message = models.TextField(blank=True)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_logs",
    )
    order = models.ForeignKey(
        "orders.Order",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="sms_logs",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "لاگ پیامک"
        verbose_name_plural = "لاگ‌های پیامک"
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["template_code", "created_at"]),
        ]

    def __str__(self):
        return f"{self.recipient} — {self.status}"
