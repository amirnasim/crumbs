from django.apps import AppConfig


class IntelligenceConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "intelligence"
    verbose_name = "هوش تجاری"

    def ready(self):
        from . import admin_urls  # noqa: F401
