from django.apps import AppConfig


class GrowthConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "growth"
    verbose_name = "رشد و بازاریابی"

    def ready(self):
        from . import signals  # noqa: F401
        from . import referral_signals  # noqa: F401
        from . import admin_urls  # noqa: F401
