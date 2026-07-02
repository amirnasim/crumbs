from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "core"
    verbose_name = "هسته"

    def ready(self):
        from .admin_branding import configure_admin_site

        configure_admin_site()
        from . import admin_urls  # noqa: F401
