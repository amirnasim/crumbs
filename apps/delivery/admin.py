from django.contrib import admin

from delivery.models import DeliveryZone, OrderStatusLog


@admin.register(DeliveryZone)
class DeliveryZoneAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "delivery_fee",
        "express_fee",
        "min_order_amount",
        "free_delivery_threshold",
        "is_active",
    )
    list_filter = ("is_active", "code")
    search_fields = ("name", "code", "cities", "states")


@admin.register(OrderStatusLog)
class OrderStatusLogAdmin(admin.ModelAdmin):
    list_display = ("order", "from_status", "to_status", "actor", "created_at")
    list_filter = ("to_status",)
    search_fields = ("order__order_number",)
    readonly_fields = ("order", "from_status", "to_status", "note", "actor", "created_at")
