from django.contrib import admin
from django.shortcuts import render
from django.utils import timezone

from intelligence.demand_service import DemandForecastService
from intelligence.insights_service import InsightsService
from intelligence.inventory_optimization_service import InventoryOptimizationService
from intelligence.models import ProductBakeRecommendation, ProductDemandForecast


def intelligence_dashboard(request):
    payload = InsightsService.get_dashboard_payload()
    today = payload["live"]
    forecasts = list(
        ProductDemandForecast.objects.filter(window_days=7)
        .select_related("product")
        .order_by("-predicted_units")[:10]
    )
    bake_recs = list(
        ProductBakeRecommendation.objects.filter(recommendation_date=timezone.localdate())
        .select_related("product")
        .order_by("-suggested_bake_qty")[:15]
    )
    low_stock = InventoryOptimizationService.low_stock_warnings()
    overstock = InventoryOptimizationService.overstock_risks()
    weekday = DemandForecastService.weekday_patterns(days=30)

    context = {
        **admin.site.each_context(request),
        "title": "Intelligence Dashboard",
        "payload": payload,
        "today": today,
        "forecasts": forecasts,
        "bake_recs": bake_recs,
        "low_stock": low_stock,
        "overstock": overstock,
        "weekday_patterns": weekday,
    }
    return render(request, "admin/intelligence/dashboard.html", context)
