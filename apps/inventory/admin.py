from django.contrib import admin

from core.admin_mixins import NoBulkDeleteMixin, NoDeleteMixin
from inventory.models import DailyProductionCapacity, ProductInventory, StockReservation


@admin.register(ProductInventory)
class ProductInventoryAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "stock_quantity",
        "reserved_quantity",
        "available_display",
        "updated_at",
    )
    list_filter = ("track_stock", "allow_preorder", "updated_at")
    search_fields = ("product__name",)
    readonly_fields = ("reserved_quantity", "available_display", "updated_at")
    fieldsets = (
        (
            "موجودی",
            {
                "fields": (
                    "product",
                    "track_stock",
                    "stock_quantity",
                    "reserved_quantity",
                    "available_display",
                    "low_stock_threshold",
                    "allow_preorder",
                    "updated_at",
                )
            },
        ),
    )

    @admin.display(description="قابل فروش")
    def available_display(self, obj):
        return obj.available_quantity


@admin.register(DailyProductionCapacity)
class DailyProductionCapacityAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "production_date",
        "max_units",
        "reserved_units",
        "fulfilled_units",
        "available_units",
    )
    list_filter = ("production_date",)
    search_fields = ("product__name",)
    date_hierarchy = "production_date"


@admin.register(StockReservation)
class StockReservationAdmin(NoBulkDeleteMixin, admin.ModelAdmin):
    list_display = (
        "product",
        "order",
        "quantity",
        "production_date",
        "status",
        "expires_at",
        "created_at",
    )
    list_filter = ("status", "production_date")
    search_fields = ("order__order_number", "product__name")
    readonly_fields = ("created_at", "updated_at")
