from django.contrib import admin
from django.urls import path

from growth.admin_views import analytics_dashboard, growth_control_panel


def register_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path(
                "analytics/",
                admin.site.admin_view(analytics_dashboard),
                name="crumbs_analytics",
            ),
            path(
                "growth/",
                admin.site.admin_view(growth_control_panel),
                name="crumbs_growth_panel",
            ),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls


register_admin_urls()
