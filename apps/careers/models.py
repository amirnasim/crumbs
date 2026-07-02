from django.core.validators import FileExtensionValidator, MaxValueValidator, MinValueValidator
from django.db import models

from careers.constants import MAX_AGE, MIN_AGE


def career_resume_upload_path(instance, filename: str) -> str:
    return f"careers/resumes/{filename}"


class CareerApplication(models.Model):
    class DesiredPosition(models.TextChoices):
        BARISTA = "barista", "باریستا"
        CASHIER = "cashier", "صندوق‌دار / فروشنده"
        COLD_BAR = "cold_bar", "بار سرد"
        WAITER = "waiter", "سالن کار"
        KITCHEN_STAFF = "kitchen_staff", "نیروی آشپزخانه"
        BAKER = "baker", "بیکر"
        PASTRY_ASSISTANT = "pastry_assistant", "کمک بیکر"
        SHIFT_SUPERVISOR = "shift_supervisor", "سرپرست شیفت"
        CLEANER = "cleaner", "خدمات و نظافت"

    class EmploymentType(models.TextChoices):
        FULL_TIME = "full_time", "تمام‌وقت"
        PART_TIME = "part_time", "پاره‌وقت"

    class Status(models.TextChoices):
        NEW = "new", "New"
        REVIEWING = "reviewing", "Reviewing"
        INTERVIEW = "interview", "Interview"
        REJECTED = "rejected", "Rejected"
        HIRED = "hired", "Hired"

    full_name = models.CharField(max_length=120, verbose_name="نام و نام خانوادگی")
    phone = models.CharField(max_length=30, verbose_name="شماره تماس")
    email = models.EmailField(verbose_name="ایمیل")
    age = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(MIN_AGE), MaxValueValidator(MAX_AGE)],
        verbose_name="سن",
    )
    residential_area = models.CharField(max_length=120, verbose_name="منطقه زندگی")
    desired_position = models.CharField(
        max_length=32,
        choices=DesiredPosition.choices,
        db_index=True,
        verbose_name="موقعیت شغلی",
    )
    employment_type = models.CharField(
        max_length=16,
        choices=EmploymentType.choices,
        verbose_name="نوع همکاری",
    )
    years_of_experience = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(0)],
        verbose_name="سابقه کار (سال)",
    )
    relevant_experience = models.TextField(verbose_name="سابقه کار مرتبط")
    hr_answers = models.JSONField(default=dict, blank=True, verbose_name="پاسخ‌های HR")
    resume_file = models.FileField(
        upload_to=career_resume_upload_path,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=["pdf"])],
        verbose_name="رزومه",
    )
    status = models.CharField(
        max_length=16,
        choices=Status.choices,
        default=Status.NEW,
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "درخواست همکاری"
        verbose_name_plural = "درخواست‌های همکاری"

    def __str__(self) -> str:
        return f"{self.full_name} — {self.get_desired_position_display()}"
