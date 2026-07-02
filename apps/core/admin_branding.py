"""Persian-first Django admin site branding."""

from django.apps import apps
from django.contrib import admin
from django.contrib.auth.models import Group, User


def configure_admin_site() -> None:
    admin.site.site_header = "مدیریت Crumbs"
    admin.site.site_title = "پنل مدیریت Crumbs"
    admin.site.index_title = "داشبورد مدیریت"

    try:
        auth_config = apps.get_app_config("auth")
        auth_config.verbose_name = "احراز هویت"
    except LookupError:
        pass

    User._meta.verbose_name = "کاربر"
    User._meta.verbose_name_plural = "کاربران"
    Group._meta.verbose_name = "گروه"
    Group._meta.verbose_name_plural = "گروه‌ها"
