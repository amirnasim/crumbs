from django.contrib import admin, messages

from growth.models import (
    AbandonedCartTracker,
    Coupon,
    CouponRedemption,
    CustomerCLVProfile,
    CustomerSegment,
    CustomerSegmentMembership,
    DailyRevenueSnapshot,
    FunnelAnalyticsSnapshot,
    GrowthEvent,
    PromotionCampaign,
    PromotionRule,
    Referral,
    ReferralCode,
    RevenueAttribution,
)
from growth.services import send_promotion_campaign


@admin.register(Coupon)
class CouponAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "discount_type",
        "discount_value",
        "is_active",
        "usage_count",
        "usage_limit_global",
        "valid_until",
        "created_at",
    )
    list_filter = ("discount_type", "campaign_type", "is_active", "created_at")
    search_fields = ("code", "name")
    readonly_fields = ("usage_count", "created_at", "updated_at")
    fieldsets = (
        (
            "کوپن",
            {
                "fields": (
                    "code",
                    "name",
                    "campaign_type",
                    "is_active",
                )
            },
        ),
        (
            "تخفیف",
            {
                "fields": (
                    "discount_type",
                    "discount_value",
                    "min_order_amount",
                    "max_discount_amount",
                    "stackable",
                )
            },
        ),
        (
            "محدودیت استفاده",
            {
                "fields": (
                    "usage_count",
                    "usage_limit_global",
                    "usage_limit_per_user",
                    "valid_from",
                    "valid_until",
                )
            },
        ),
        (
            "زمان‌بندی",
            {
                "fields": ("created_at", "updated_at"),
                "classes": ("collapse",),
            },
        ),
    )


@admin.register(CouponRedemption)
class CouponRedemptionAdmin(admin.ModelAdmin):
    list_display = ("coupon", "order", "user", "discount_amount", "created_at")
    list_filter = ("coupon", "created_at")
    search_fields = ("coupon__code", "order__order_number", "user__username")
    readonly_fields = ("coupon", "order", "user", "discount_amount", "created_at")


@admin.register(ReferralCode)
class ReferralCodeAdmin(admin.ModelAdmin):
    list_display = ("code", "user", "is_active", "created_at")
    search_fields = ("code", "user__username", "user__email")
    readonly_fields = ("created_at",)


@admin.register(Referral)
class ReferralAdmin(admin.ModelAdmin):
    list_display = (
        "referrer",
        "referred_user",
        "status",
        "referrer_reward_points",
        "first_order",
        "created_at",
    )
    list_filter = ("status",)
    search_fields = ("referrer__username", "referred_user__username", "referral_code__code")


@admin.register(PromotionRule)
class PromotionRuleAdmin(admin.ModelAdmin):
    list_display = ("name", "rule_type", "priority", "is_active", "valid_from", "valid_until")
    list_filter = ("rule_type", "is_active")
    search_fields = ("name",)


@admin.register(GrowthEvent)
class GrowthEventAdmin(admin.ModelAdmin):
    list_display = ("event_type", "user", "product", "order", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("session_key", "user__username")
    readonly_fields = ("event_type", "user", "session_key", "product", "cart", "order", "metadata", "created_at")


@admin.register(CustomerCLVProfile)
class CustomerCLVProfileAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "revenue_tier",
        "frequency_tag",
        "lifetime_revenue",
        "order_count",
        "clv_score",
        "updated_at",
    )
    list_filter = ("revenue_tier", "frequency_tag")
    search_fields = ("user__username", "user__email")
    readonly_fields = (
        "lifetime_revenue",
        "order_count",
        "avg_order_value",
        "clv_score",
        "revenue_tier",
        "frequency_tag",
        "last_order_at",
        "updated_at",
    )


@admin.register(RevenueAttribution)
class RevenueAttributionAdmin(admin.ModelAdmin):
    list_display = ("order", "source_type", "source_label", "attributed_amount", "created_at")
    list_filter = ("source_type",)
    search_fields = ("order__order_number", "source_label", "source_id")
    readonly_fields = ("order", "source_type", "source_id", "source_label", "attributed_amount", "metadata", "created_at")


@admin.register(DailyRevenueSnapshot)
class DailyRevenueSnapshotAdmin(admin.ModelAdmin):
    list_display = ("report_date", "created_at")
    readonly_fields = ("report_date", "payload", "created_at")


@admin.register(FunnelAnalyticsSnapshot)
class FunnelAnalyticsSnapshotAdmin(admin.ModelAdmin):
    list_display = ("report_date", "created_at")
    readonly_fields = ("report_date", "payload", "created_at")


@admin.register(AbandonedCartTracker)
class AbandonedCartTrackerAdmin(admin.ModelAdmin):
    list_display = (
        "cart",
        "phone",
        "item_count",
        "subtotal",
        "status",
        "funnel_step",
        "reminder_count",
        "last_activity_at",
    )
    list_filter = ("status", "reminder_count", "funnel_step")
    search_fields = ("phone", "session_key", "user__username", "user__email")
    readonly_fields = (
        "cart",
        "user",
        "phone",
        "session_key",
        "item_count",
        "subtotal",
        "last_activity_at",
        "reminder_count",
        "last_reminder_at",
        "funnel_step",
        "offered_coupon",
        "sms_conversion_tracked",
        "recovered_order",
        "created_at",
        "updated_at",
    )


@admin.register(CustomerSegment)
class CustomerSegmentAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "is_active")
    list_filter = ("is_active",)
    search_fields = ("code", "name")


@admin.register(CustomerSegmentMembership)
class CustomerSegmentMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "segment", "assigned_at")
    list_filter = ("segment",)
    search_fields = ("user__username", "user__email")


@admin.register(PromotionCampaign)
class PromotionCampaignAdmin(admin.ModelAdmin):
    list_display = ("name", "segment", "status", "sent_count", "sent_at", "created_at")
    list_filter = ("status", "segment")
    search_fields = ("name", "message")
    actions = ("send_campaign_sms",)

    @admin.action(description="Send SMS promotion to segment")
    def send_campaign_sms(self, request, queryset):
        for campaign in queryset:
            send_promotion_campaign(campaign)
        self.message_user(
            request,
            "Promotion campaign queued for background SMS delivery.",
            messages.SUCCESS,
        )
