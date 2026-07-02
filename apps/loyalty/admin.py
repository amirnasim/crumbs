from django.contrib import admin

from .models import LoyaltyAccount, LoyaltyTransaction


class LoyaltyTransactionInline(admin.TabularInline):
    model = LoyaltyTransaction
    extra = 0
    readonly_fields = ("transaction_type", "points", "balance_after", "order", "description", "created_at")
    can_delete = False
    verbose_name = "تراکنش"
    verbose_name_plural = "تراکنش‌ها"

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LoyaltyAccount)
class LoyaltyAccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "tier",
        "points",
        "lifetime_points",
        "lifetime_spend",
        "updated_at",
    )
    list_filter = ("tier",)
    search_fields = ("user__username", "user__email", "user__first_name", "user__last_name")
    readonly_fields = ("updated_at",)
    inlines = (LoyaltyTransactionInline,)


@admin.register(LoyaltyTransaction)
class LoyaltyTransactionAdmin(admin.ModelAdmin):
    list_display = (
        "account",
        "transaction_type",
        "points",
        "balance_after",
        "order",
        "created_at",
    )
    list_filter = ("transaction_type", "created_at")
    search_fields = ("account__user__username", "description", "order__order_number")
    readonly_fields = ("account", "transaction_type", "points", "balance_after", "order", "description", "created_at")
