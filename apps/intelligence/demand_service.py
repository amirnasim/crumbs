"""Daily demand aggregation and statistical forecasting."""

from collections import defaultdict
from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.utils import timezone

from growth.services import PAID_PAYMENT_STATUSES
from intelligence.models import ProductDailyStats, ProductDemandForecast
from orders.models import OrderItem
from products.models import Product


class DemandForecastService:
    @classmethod
    def aggregate_daily_stats(cls, stat_date=None) -> int:
        stat_date = stat_date or timezone.localdate()
        start = timezone.make_aware(datetime.combine(stat_date, datetime.min.time()))
        end = start + timedelta(days=1)

        items = (
            OrderItem.objects.filter(
                order__payment_status__in=PAID_PAYMENT_STATUSES,
                order__created_at__gte=start,
                order__created_at__lt=end,
            )
            .select_related("order")
            .values("product_id", "quantity", "line_total", "order__created_at")
        )

        buckets: dict[int, dict] = defaultdict(
            lambda: {
                "units": 0,
                "revenue": Decimal("0"),
                "orders": set(),
                "hours": defaultdict(int),
            }
        )

        for row in items:
            pid = row["product_id"]
            buckets[pid]["units"] += row["quantity"]
            buckets[pid]["revenue"] += row["line_total"]
            buckets[pid]["orders"].add(row["order__created_at"].date())
            hour = timezone.localtime(row["order__created_at"]).hour
            buckets[pid]["hours"][hour] += row["quantity"]

        count = 0
        weekday = stat_date.weekday()
        for pid, data in buckets.items():
            peak_hour = max(data["hours"], key=data["hours"].get) if data["hours"] else None
            ProductDailyStats.objects.update_or_create(
                product_id=pid,
                stat_date=stat_date,
                defaults={
                    "units_sold": data["units"],
                    "revenue": data["revenue"],
                    "order_count": len(data["orders"]),
                    "peak_hour": peak_hour,
                    "weekday": weekday,
                    "hourly_distribution": dict(data["hours"]),
                },
            )
            count += 1
        return count

    @classmethod
    def generate_forecasts(cls, forecast_date=None, windows: tuple[int, ...] = (7, 14)) -> int:
        forecast_date = forecast_date or (timezone.localdate() + timedelta(days=1))
        count = 0

        for product in Product.objects.filter(availability_status=Product.AvailabilityStatus.AVAILABLE):
            for window in windows:
                forecast = cls._forecast_product(product, forecast_date, window)
                if forecast is None:
                    continue
                ProductDemandForecast.objects.update_or_create(
                    product=product,
                    forecast_for_date=forecast_date,
                    window_days=window,
                    defaults=forecast,
                )
                count += 1
        return count

    @classmethod
    def _forecast_product(cls, product, forecast_date, window_days: int) -> dict | None:
        since = forecast_date - timedelta(days=window_days)
        stats = ProductDailyStats.objects.filter(product=product, stat_date__gte=since, stat_date__lt=forecast_date)

        if not stats.exists():
            return None

        total_units = stats.aggregate(total=Sum("units_sold"))["total"] or 0
        days_with_sales = stats.count()
        if days_with_sales == 0:
            return None

        moving_avg = Decimal(total_units) / Decimal(days_with_sales)

        weekday_stats = stats.filter(weekday=forecast_date.weekday())
        weekday_units = weekday_stats.aggregate(total=Sum("units_sold"))["total"] or 0
        weekday_days = weekday_stats.count() or 1
        weekday_avg = Decimal(weekday_units) / Decimal(weekday_days)
        weekday_factor = (weekday_avg / moving_avg) if moving_avg else Decimal("1")

        predicted = (moving_avg * weekday_factor).quantize(Decimal("0.01"))

        return {
            "predicted_units": max(predicted, Decimal("0")),
            "historical_avg": moving_avg.quantize(Decimal("0.01")),
            "weekday_factor": weekday_factor.quantize(Decimal("0.0001")),
        }

    @classmethod
    def peak_hour_analysis(cls, days: int = 30) -> list[dict]:
        since = timezone.localdate() - timedelta(days=days)
        stats = ProductDailyStats.objects.filter(stat_date__gte=since, peak_hour__isnull=False)
        hours: dict[int, int] = defaultdict(int)
        for row in stats.values("peak_hour").annotate(c=Count("id")):
            hours[row["peak_hour"]] += row["c"]
        return [{"hour": h, "count": c} for h, c in sorted(hours.items())]

    @classmethod
    def weekday_patterns(cls, days: int = 30) -> list[dict]:
        since = timezone.localdate() - timedelta(days=days)
        rows = (
            ProductDailyStats.objects.filter(stat_date__gte=since)
            .values("weekday")
            .annotate(units=Sum("units_sold"), revenue=Sum("revenue"))
            .order_by("weekday")
        )
        weekday_names = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        return [
            {
                "weekday": row["weekday"],
                "label": weekday_names[row["weekday"]] if row["weekday"] is not None else "?",
                "units": row["units"] or 0,
                "revenue": str(row["revenue"] or 0),
            }
            for row in rows
        ]
