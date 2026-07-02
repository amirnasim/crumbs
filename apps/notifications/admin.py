from django.contrib import admin

from .models import SMSLog, SMSTemplate


@admin.register(SMSTemplate)
class SMSTemplateAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "category", "is_active", "updated_at")
    list_filter = ("category", "is_active")
    search_fields = ("code", "name", "body")


@admin.register(SMSLog)
class SMSLogAdmin(admin.ModelAdmin):
    list_display = ("recipient", "template_code", "status", "provider", "created_at")
    list_filter = ("status", "provider", "template_code", "created_at")
    search_fields = ("recipient", "message", "provider_message_id")
    readonly_fields = (
        "provider",
        "template_code",
        "recipient",
        "message",
        "status",
        "provider_message_id",
        "error_message",
        "user",
        "order",
        "metadata",
        "created_at",
    )
