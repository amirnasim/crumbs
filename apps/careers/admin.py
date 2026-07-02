from django.contrib import admin, messages
from django.utils.html import format_html_join

from careers.constants import HR_QUESTIONS
from careers.models import CareerApplication
from core.admin_labels import CAREER_STATUS_FA, fa_label
from core.admin_mixins import NoDeleteMixin

HR_QUESTION_LABELS = dict(HR_QUESTIONS)


@admin.register(CareerApplication)
class CareerApplicationAdmin(NoDeleteMixin, admin.ModelAdmin):
    list_display = (
        "full_name",
        "desired_position",
        "employment_type",
        "age",
        "residential_area",
        "phone",
        "email",
        "status_fa",
        "created_at",
    )
    list_filter = ("status", "desired_position", "employment_type", "created_at")
    search_fields = ("full_name", "phone", "email", "residential_area")
    readonly_fields = ("created_at", "hr_answers_display")
    actions = (
        "mark_reviewing",
        "mark_interview",
        "mark_rejected",
        "mark_hired",
    )
    fieldsets = (
        (
            "اطلاعات فردی",
            {
                "fields": (
                    "full_name",
                    "phone",
                    "email",
                    "age",
                    "residential_area",
                )
            },
        ),
        (
            "اطلاعات شغلی",
            {
                "fields": (
                    "desired_position",
                    "employment_type",
                    "years_of_experience",
                    "relevant_experience",
                )
            },
        ),
        (
            "سؤالات استخدامی",
            {
                "fields": ("hr_answers_display",),
            },
        ),
        (
            "رزومه",
            {
                "fields": ("resume_file",),
            },
        ),
        (
            "وضعیت بررسی",
            {
                "fields": (
                    "status",
                    "created_at",
                )
            },
        ),
    )

    @admin.display(description="وضعیت", ordering="status")
    def status_fa(self, obj):
        return fa_label(CAREER_STATUS_FA, obj.status)

    @admin.display(description="پاسخ‌های استخدامی")
    def hr_answers_display(self, obj):
        if not obj.hr_answers:
            return "—"
        rows = []
        for key, answer in obj.hr_answers.items():
            label = HR_QUESTION_LABELS.get(key, key.replace("_", " ").title())
            rows.append((label, answer))
        return format_html_join(
            "",
            "<p><strong>{}</strong><br>{}</p>",
            rows,
        )

    @admin.action(description="علامت‌گذاری به عنوان در حال بررسی")
    def mark_reviewing(self, request, queryset):
        updated = queryset.update(status=CareerApplication.Status.REVIEWING)
        self.message_user(request, f"Marked {updated} application(s) as reviewing.", messages.SUCCESS)

    @admin.action(description="علامت‌گذاری برای مصاحبه")
    def mark_interview(self, request, queryset):
        updated = queryset.update(status=CareerApplication.Status.INTERVIEW)
        self.message_user(request, f"Marked {updated} application(s) for interview.", messages.SUCCESS)

    @admin.action(description="علامت‌گذاری به عنوان رد شده")
    def mark_rejected(self, request, queryset):
        updated = queryset.update(status=CareerApplication.Status.REJECTED)
        self.message_user(request, f"Marked {updated} application(s) as rejected.", messages.SUCCESS)

    @admin.action(description="علامت‌گذاری به عنوان پذیرفته‌شده")
    def mark_hired(self, request, queryset):
        updated = queryset.update(status=CareerApplication.Status.HIRED)
        self.message_user(request, f"Marked {updated} application(s) as hired.", messages.SUCCESS)
