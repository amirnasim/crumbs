import json

from django.contrib import admin
from django.utils.html import format_html

from core.admin_labels import PAYMENT_PROVIDER_FA, PAYMENT_STATUS_FA, fa_label
from core.admin_mixins import NoBulkDeleteMixin
from core.observability import scrub_mapping

from .models import Payment, PaymentEvent


def _safe_metadata_display(metadata: dict) -> str:
    if not metadata:
        return "—"
    cleaned = scrub_mapping(dict(metadata))
    return json.dumps(cleaned, ensure_ascii=False, indent=2)


@admin.register(Payment)
class PaymentAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "order_link",
        "provider_fa",
        "status_fa",
        "amount",
        "created_at",
    )
    list_filter = ("provider", "status", "created_at")
    search_fields = (
        "id",
        "order__order_number",
        "provider_payment_id",
        "provider_checkout_session_id",
    )
    readonly_fields = (
        "order",
        "provider",
        "status",
        "amount",
        "currency",
        "provider_payment_id",
        "provider_checkout_session_id",
        "checkout_link",
        "failure_message",
        "metadata_safe",
        "created_at",
        "updated_at",
    )
    fieldsets = (
        (
            "پرداخت",
            {
                "fields": (
                    "order",
                    "provider",
                    "status",
                    "amount",
                    "currency",
                    "created_at",
                    "updated_at",
                )
            },
        ),
        (
            "ارجاعات ارائه‌دهنده",
            {
                "fields": (
                    "provider_payment_id",
                    "provider_checkout_session_id",
                    "checkout_link",
                    "failure_message",
                )
            },
        ),
        (
            "متادیتا",
            {
                "classes": ("collapse",),
                "fields": ("metadata_safe",),
            },
        ),
    )

    @admin.display(description="سفارش", ordering="order")
    def order_link(self, obj):
        return obj.order.order_number

    @admin.display(description="ارائه‌دهنده", ordering="provider")
    def provider_fa(self, obj):
        return fa_label(PAYMENT_PROVIDER_FA, obj.provider)

    @admin.display(description="وضعیت", ordering="status")
    def status_fa(self, obj):
        return fa_label(PAYMENT_STATUS_FA, obj.status)

    @admin.display(description="لینک پرداخت")
    def checkout_link(self, obj):
        if obj.checkout_url:
            return format_html('<a href="{}" target="_blank">باز کردن درگاه</a>', obj.checkout_url)
        return "—"

    @admin.display(description="متادیتا (بدون اطلاعات حساس)")
    def metadata_safe(self, obj):
        return _safe_metadata_display(obj.metadata)


@admin.register(PaymentEvent)
class PaymentEventAdmin(admin.ModelAdmin):
    list_display = (
        "event_id",
        "provider_fa",
        "event_type",
        "processed",
        "created_at",
    )
    list_filter = ("provider", "event_type", "processed", "created_at")
    search_fields = ("event_id", "event_type")
    readonly_fields = (
        "provider",
        "event_id",
        "event_type",
        "payload_safe",
        "processed",
        "processing_error",
        "processed_at",
        "created_at",
    )

    @admin.display(description="ارائه‌دهنده", ordering="provider")
    def provider_fa(self, obj):
        return fa_label(PAYMENT_PROVIDER_FA, obj.provider)

    @admin.display(description="داده خام (فیلتر شده)")
    def payload_safe(self, obj):
        if not obj.payload:
            return "—"
        cleaned = scrub_mapping(dict(obj.payload))
        return json.dumps(cleaned, ensure_ascii=False, indent=2)
