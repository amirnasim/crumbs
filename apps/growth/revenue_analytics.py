"""Revenue and funnel analytics aggregation."""

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from growth.attribution_service import AttributionService
from growth.conversion_service import ConversionService
from growth.models import (
    CouponRedemption,
    DailyRevenueSnapshot,
    FunnelAnalyticsSnapshot,
    Referral,
    RevenueAttribution,
)
from growth.services import PAID_PAYMENT_STATUSES, get_analytics_snapshot
from orders.models import Order


def build_daily_revenue_snapshot(report_date=None) -> dict:
    report_date = report_date or timezone.localdate()
    start = timezone.make_aware(datetime.combine(report_date, datetime.min.time()))
    end = start + timedelta(days=1)

    paid_orders = Order.objects.filter(
        payment_status__in=PAID_PAYMENT_STATUSES,
        created_at__gte=start,
        created_at__lt=end,
    )
    gross_revenue = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0.00")
    discount_total = paid_orders.aggregate(total=Sum("discount_amount"))["total"] or Decimal("0.00")
    order_count = paid_orders.count()

    repeat_customers = (
        paid_orders.filter(user__isnull=False)
        .values("user")
        .annotate(c=Count("id"))
        .filter(c__gt=1)
        .count()
    )
    unique_customers = paid_orders.filter(user__isnull=False).values("user").distinct().count()
    repeat_rate = (repeat_customers / unique_customers * 100) if unique_customers else 0

    coupon_performance = AttributionService.coupon_performance(since=start)
    sms_attributed = (
        RevenueAttribution.objects.filter(
            source_type=RevenueAttribution.SourceType.SMS,
            created_at__gte=start,
            created_at__lt=end,
        ).aggregate(total=Sum("attributed_amount"))["total"]
        or Decimal("0.00")
    )

    return {
        "report_date": str(report_date),
        "gross_revenue": str(gross_revenue),
        "discount_total": str(discount_total),
        "net_revenue": str(gross_revenue),
        "order_count": order_count,
        "avg_order_value": str(gross_revenue / order_count if order_count else Decimal("0")),
        "repeat_customer_rate": round(repeat_rate, 2),
        "coupon_redemptions": CouponRedemption.objects.filter(created_at__gte=start, created_at__lt=end).count(),
        "referral_conversions": Referral.objects.filter(
            rewarded_at__gte=start,
            rewarded_at__lt=end,
            status=Referral.Status.REWARDED,
        ).count(),
        "sms_attributed_revenue": str(sms_attributed),
        "coupon_performance": coupon_performance,
    }


def build_funnel_snapshot(report_date=None) -> dict:
    report_date = report_date or timezone.localdate()
    start = timezone.make_aware(datetime.combine(report_date, datetime.min.time()))
    end = start + timedelta(days=1)
    funnel = ConversionService.aggregate_funnel(start, end)
    base = get_analytics_snapshot(days=1)
    funnel["abandoned_active"] = base["abandoned_active"]
    funnel["abandoned_recovered"] = base["abandoned_recovered"]
    funnel["report_date"] = str(report_date)
    return funnel


def persist_daily_revenue_snapshot(report_date=None) -> DailyRevenueSnapshot:
    report_date = report_date or timezone.localdate()
    payload = build_daily_revenue_snapshot(report_date)
    snapshot, _ = DailyRevenueSnapshot.objects.update_or_create(
        report_date=report_date,
        defaults={"payload": payload},
    )
    return snapshot


def persist_funnel_snapshot(report_date=None) -> FunnelAnalyticsSnapshot:
    report_date = report_date or timezone.localdate()
    payload = build_funnel_snapshot(report_date)
    snapshot, _ = FunnelAnalyticsSnapshot.objects.update_or_create(
        report_date=report_date,
        defaults={"payload": payload},
    )
    return snapshot


def get_growth_dashboard_snapshot(days: int = 30) -> dict:
    since = timezone.now() - timedelta(days=days)
    base = get_analytics_snapshot(days=days)
    funnel = ConversionService.aggregate_funnel(since)
    latest_revenue = DailyRevenueSnapshot.objects.order_by("-report_date").first()
    latest_funnel = FunnelAnalyticsSnapshot.objects.order_by("-report_date").first()

    return {
        **base,
        **funnel,
        "coupon_performance": AttributionService.coupon_performance(since=since),
        "referral_leaderboard": AttributionService.referral_leaderboard(),
        "latest_revenue_snapshot": latest_revenue.payload if latest_revenue else {},
        "latest_funnel_snapshot": latest_funnel.payload if latest_funnel else {},
    }
