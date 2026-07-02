from django.contrib import admin

from core.models import BackgroundTaskLog, DailyAnalyticsSnapshot


@admin.register(BackgroundTaskLog)
class BackgroundTaskLogAdmin(admin.ModelAdmin):
    list_display = ("task_name", "status", "retry_count", "queue", "created_at", "completed_at")
    list_filter = ("status", "task_name")
    search_fields = ("task_id", "idempotency_key", "task_name", "error_message")
    readonly_fields = (
        "task_name",
        "task_id",
        "idempotency_key",
        "queue",
        "status",
        "payload",
        "result",
        "error_message",
        "retry_count",
        "created_at",
        "updated_at",
        "completed_at",
    )


@admin.register(DailyAnalyticsSnapshot)
class DailyAnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ("report_date", "created_at")
    readonly_fields = ("report_date", "payload", "created_at")
