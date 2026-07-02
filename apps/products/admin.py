from django.contrib import admin
from django.utils.html import format_html

from core.admin_labels import PRODUCT_AVAILABILITY_FA, fa_label
from core.performance import invalidate_catalog_cache

from .models import Category, Product


class CatalogCacheInvalidationMixin:
    def _invalidate_catalog(self, obj=None):
        invalidate_catalog_cache()
        if obj is not None:
            from django.core.cache import cache

            cache.delete("crumbs:catalog:products:all")
            if isinstance(obj, Product) and obj.category_id:
                cache.delete(f"crumbs:catalog:products:{obj.category.slug}")
            if isinstance(obj, Category):
                cache.delete(f"crumbs:catalog:products:{obj.slug}")

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        self._invalidate_catalog(obj)

    def delete_model(self, request, obj):
        super().delete_model(request, obj)
        self._invalidate_catalog(obj)


@admin.register(Category)
class CategoryAdmin(CatalogCacheInvalidationMixin, admin.ModelAdmin):
    list_display = ("name", "slug", "product_count", "image_preview")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("image_preview",)

    @admin.display(description="تعداد محصول")
    def product_count(self, obj):
        return obj.products.count()

    @admin.display(description="پیش‌نمایش")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 80px; border-radius: 4px;" />',
                obj.image.url,
            )
        return "—"


@admin.register(Product)
class ProductAdmin(CatalogCacheInvalidationMixin, admin.ModelAdmin):
    list_display = (
        "thumbnail_preview",
        "name",
        "category",
        "price",
        "availability_fa",
        "is_featured",
        "stock_summary",
        "updated_at",
    )
    list_filter = ("is_featured", "availability_status", "category", "created_at")
    search_fields = ("name", "slug", "description", "ingredients")
    prepopulated_fields = {"slug": ("name",)}
    readonly_fields = ("created_at", "updated_at", "image_preview")
    autocomplete_fields = ("category",)
    fieldsets = (
        (
            "اطلاعات اصلی",
            {
                "fields": (
                    "category",
                    "name",
                    "slug",
                    "description",
                    "ingredients",
                )
            },
        ),
        (
            "قیمت و فروش",
            {
                "fields": (
                    "price",
                    "availability_status",
                    "is_featured",
                )
            },
        ),
        (
            "تصویر و رسانه",
            {
                "fields": (
                    "image",
                    "image_preview",
                )
            },
        ),
        (
            "وضعیت نمایش",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )

    @admin.display(description="تصویر")
    def thumbnail_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 48px; max-width: 48px; border-radius: 4px;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="پیش‌نمایش")
    def image_preview(self, obj):
        if obj.image:
            return format_html(
                '<img src="{}" style="max-height: 160px; border-radius: 4px;" />',
                obj.image.url,
            )
        return "—"

    @admin.display(description="وضعیت", ordering="availability_status")
    def availability_fa(self, obj):
        return fa_label(PRODUCT_AVAILABILITY_FA, obj.availability_status)

    @admin.display(description="موجودی")
    def stock_summary(self, obj):
        inventory = getattr(obj, "inventory", None)
        if inventory is None:
            return "—"
        if not inventory.track_stock:
            return "نامحدود"
        return inventory.available_quantity
