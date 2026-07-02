from django.contrib import admin

from .models import Cart, CartItem


class CartItemInline(admin.TabularInline):
    model = CartItem
    extra = 0
    autocomplete_fields = ("product",)
    readonly_fields = ("line_total_display", "created_at", "updated_at")
    fields = ("product", "quantity", "line_total_display", "created_at", "updated_at")

    @admin.display(description="Line total")
    def line_total_display(self, obj):
        if obj.pk:
            return obj.line_total
        return "—"


@admin.register(Cart)
class CartAdmin(admin.ModelAdmin):
    list_display = ("id", "owner_display", "total_items_display", "subtotal_display", "updated_at")
    list_filter = ("updated_at",)
    search_fields = ("user__username", "user__email", "session_key")
    readonly_fields = ("created_at", "updated_at", "total_items_display", "subtotal_display")
    fields = (
        "user",
        "session_key",
        "applied_coupon_code",
        "referral_code",
        "total_items_display",
        "subtotal_display",
        "created_at",
        "updated_at",
    )
    inlines = (CartItemInline,)

    @admin.display(description="Owner")
    def owner_display(self, obj):
        if obj.user_id:
            return obj.user.get_username()
        return f"Session {obj.session_key}"

    @admin.display(description="Items")
    def total_items_display(self, obj):
        return obj.total_items

    @admin.display(description="Subtotal")
    def subtotal_display(self, obj):
        return obj.get_subtotal()
