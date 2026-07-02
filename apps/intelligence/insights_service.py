"""Revenue optimization insights and intelligence snapshots."""

from datetime import timedelta

from django.db import models
from django.db.models import Count
from django.utils import timezone

from growth.conversion_service import ConversionService
from growth.services import get_analytics_snapshot
from intelligence.models import IntelligenceSnapshot, ProductDailyStats, UpsellImpression
from products.models import Product


class InsightsService:
    @classmethod
    def build_daily_insights(cls) -> dict:
        since = timezone.now() - timedelta(days=30)
        base = get_analytics_snapshot(days=30)
        funnel = ConversionService.aggregate_funnel(since)

        from django.db.models import Sum

        product_stats = (
            ProductDailyStats.objects.filter(stat_date__gte=timezone.localdate() - timedelta(days=30))
            .values("product_id")
            .annotate(units=Sum("units_sold"), revenue=Sum("revenue"))
        )
        stats_list = list(product_stats)
        stats_list.sort(key=lambda x: x["revenue"] or 0, reverse=True)

        product_names = {
            p.pk: p.name
            for p in Product.objects.filter(pk__in=[s["product_id"] for s in stats_list[:20]])
        }

        best = [
            {
                "product_id": s["product_id"],
                "name": product_names.get(s["product_id"], "?"),
                "units": s["units"],
                "revenue": str(s["revenue"] or 0),
            }
            for s in stats_list[:5]
        ]
        worst = [
            {
                "product_id": s["product_id"],
                "name": product_names.get(s["product_id"], "?"),
                "units": s["units"],
                "revenue": str(s["revenue"] or 0),
            }
            for s in sorted(stats_list, key=lambda x: x["revenue"] or 0)[:5]
        ]

        margin_proxy = list(
            Product.objects.filter(availability_status=Product.AvailabilityStatus.AVAILABLE)
            .select_related("intelligence_meta")
            .order_by("-intelligence_meta__margin_boost", "-price")[:5]
            .values("id", "name", "price")
        )

        upsell_impressions = UpsellImpression.objects.filter(created_at__gte=since).count()
        upsell_conversions = UpsellImpression.objects.filter(created_at__gte=since, converted=True).count()
        upsell_rate = (upsell_conversions / upsell_impressions * 100) if upsell_impressions else 0

        bottlenecks = []
        if funnel.get("view_to_cart_rate", 100) < 10:
            bottlenecks.append("Low product view → add-to-cart conversion")
        if funnel.get("checkout_conversion_rate", 100) < 40:
            bottlenecks.append("Checkout abandonment elevated")
        if funnel.get("sms_conversion_rate", 100) < 5 and funnel.get("sms_sent", 0) > 10:
            bottlenecks.append("SMS-driven conversion below target")

        return {
            "report_date": str(timezone.localdate()),
            "revenue": str(base["revenue"]),
            "order_count": base["order_count"],
            "best_products": best,
            "worst_products": worst,
            "highest_margin_products": margin_proxy,
            "conversion_funnel": funnel,
            "bottlenecks": bottlenecks,
            "upsell_impressions": upsell_impressions,
            "upsell_conversion_rate": round(upsell_rate, 2),
            "recommendation_slots": cls._recommendation_effectiveness(since),
        }

    @classmethod
    def _recommendation_effectiveness(cls, since) -> dict:
        return {
            row["slot"]: {
                "impressions": row["impressions"],
                "conversions": row["conversions"],
            }
            for row in UpsellImpression.objects.filter(created_at__gte=since)
            .values("slot")
            .annotate(
                impressions=Count("id"),
                conversions=Count("id", filter=models.Q(converted=True)),
            )
        }

    @classmethod
    def persist_snapshot(cls, *, period=IntelligenceSnapshot.Period.DAILY) -> IntelligenceSnapshot:
        report_date = timezone.localdate()
        payload = cls.build_daily_insights()
        snapshot, _ = IntelligenceSnapshot.objects.update_or_create(
            report_date=report_date,
            period=period,
            defaults={"payload": payload},
        )
        return snapshot

    @classmethod
    def get_dashboard_payload(cls) -> dict:
        latest = IntelligenceSnapshot.objects.order_by("-report_date").first()
        live = cls.build_daily_insights()
        return {
            "live": live,
            "latest_snapshot": latest.payload if latest else {},
            "latest_snapshot_date": str(latest.report_date) if latest else None,
        }
