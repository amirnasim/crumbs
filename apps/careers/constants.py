"""Careers application constants."""

MAX_RESUME_SIZE_BYTES = 5 * 1024 * 1024
MIN_AGE = 16
MAX_AGE = 80

REQUIRED_FIELD_ERROR = "تکمیل این فیلد الزامی است."
PDF_ONLY_ERROR = "فقط فایل PDF قابل بارگذاری است."
INVALID_PDF_ERROR = "فایل رزومه باید PDF معتبر باشد."
FILE_SIZE_ERROR = "حداکثر حجم فایل ۵ مگابایت است."
PDF_MAGIC = b"%PDF-"
AGE_RANGE_ERROR = f"سن باید بین {MIN_AGE} و {MAX_AGE} سال باشد."

HR_QUESTIONS = (
    ("why_crumbs", "چرا علاقه‌مند به همکاری با Crumbs هستید؟"),
    (
        "cafe_experience",
        "آیا سابقه کار در کافه، رستوران یا مجموعه مشابه دارید؟",
    ),
    ("start_timing", "از چه زمانی می‌توانید همکاری خود را آغاز کنید؟"),
)
