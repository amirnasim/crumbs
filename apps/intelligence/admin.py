from django.contrib import admin

from intelligence.models import (
    CustomerIntelligenceProfile,
    IntelligenceSnapshot,
    ProductBakeRecommendation,
    ProductCoPurchase,
    ProductDailyStats,
    ProductDemandForecast,
    ProductIntelligenceMeta,
    UpsellImpression,
)


@admin.register(ProductIntelligenceMeta)
class ProductIntelligenceMetaAdmin(admin.ModelAdmin):
    list_display = ("product", "is_cookie", "is_coffee", "margin_boost", "updated_at")
    list_filter = ("is_cookie", "is_coffee")
    search_fields = ("product__name",)
    autocomplete_fields = ("product",)


@admin.register(ProductCoPurchase)
class ProductCoPurchaseAdmin(admin.ModelAdmin):
    list_display = ("product", "related_product", "co_count", "affinity_score", "updated_at")
    search_fields = ("product__name", "related_product__name")
    autocomplete_fields = ("product", "related_product")


@admin.register(ProductDailyStats)
class ProductDailyStatsAdmin(admin.ModelAdmin):
    list_display = ("product", "stat_date", "units_sold", "revenue", "peak_hour", "weekday")
    list_filter = ("stat_date", "weekday")
    search_fields = ("product__name",)
    readonly_fields = ("hourly_distribution", "created_at")


@admin.register(ProductDemandForecast)
class ProductDemandForecastAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "forecast_for_date",
        "window_days",
        "predicted_units",
        "historical_avg",
        "weekday_factor",
    )
    list_filter = ("forecast_for_date", "window_days")
    search_fields = ("product__name",)


@admin.register(ProductBakeRecommendation)
class ProductBakeRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "product",
        "recommendation_date",
        "suggested_bake_qty",
        "forecast_demand",
        "current_stock",
        "status",
    )
    list_filter = ("status", "recommendation_date")
    search_fields = ("product__name", "notes")
    readonly_fields = ("created_at",)


@admin.register(CustomerIntelligenceProfile)
class CustomerIntelligenceProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "engagement_score", "behavioral_tags", "discount_sensitivity", "updated_at")
    list_filter = ("engagement_score",)
    search_fields = ("user__username", "user__email")
    readonly_fields = ("behavioral_tags", "category_affinity", "preferred_product_ids", "updated_at")


@admin.register(IntelligenceSnapshot)
class IntelligenceSnapshotAdmin(admin.ModelAdmin):
    list_display = ("report_date", "period", "created_at")
    list_filter = ("period",)
    readonly_fields = ("payload", "created_at")


@admin.register(UpsellImpression)
class UpsellImpressionAdmin(admin.ModelAdmin):
    list_display = ("slot", "user", "converted", "created_at")
    list_filter = ("slot", "converted")
    readonly_fields = ("product_ids", "metadata", "conversion_order", "created_at")
