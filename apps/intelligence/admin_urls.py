from django.contrib import admin
from django.urls import path

from intelligence.admin_views import intelligence_dashboard


def register_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path(
                "intelligence/",
                admin.site.admin_view(intelligence_dashboard),
                name="crumbs_intelligence",
            ),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls


register_admin_urls()
