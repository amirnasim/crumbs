from django.contrib import admin
from django.urls import path

from core.admin_views import operations_dashboard, ops_dashboard
from core.kitchen_views import kitchen_action, kitchen_queue
from core.order_lookup_views import order_lookup
from core.pickup_views import pickup_action, pickup_screen
from core.shift_summary_views import shift_summary


def register_admin_urls():
    original_get_urls = admin.site.get_urls

    def get_urls():
        custom_urls = [
            path(
                "operations/",
                admin.site.admin_view(operations_dashboard),
                name="crumbs_operations",
            ),
            path(
                "ops/",
                admin.site.admin_view(ops_dashboard),
                name="crumbs_ops",
            ),
            path(
                "kitchen/",
                admin.site.admin_view(kitchen_queue),
                name="crumbs_kitchen",
            ),
            path(
                "kitchen/action/",
                admin.site.admin_view(kitchen_action),
                name="crumbs_kitchen_action",
            ),
            path(
                "pickup-screen/",
                admin.site.admin_view(pickup_screen),
                name="crumbs_pickup_screen",
            ),
            path(
                "pickup-screen/action/",
                admin.site.admin_view(pickup_action),
                name="crumbs_pickup_action",
            ),
            path(
                "order-lookup/",
                admin.site.admin_view(order_lookup),
                name="crumbs_order_lookup",
            ),
            path(
                "shift-summary/",
                admin.site.admin_view(shift_summary),
                name="crumbs_shift_summary",
            ),
        ]
        return custom_urls + original_get_urls()

    admin.site.get_urls = get_urls


register_admin_urls()
