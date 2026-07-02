import logging

from celery import shared_task
from django.utils import timezone

from core.tasks.base import CrumbsTask

logger = logging.getLogger("crumbs.tasks")


@shared_task(base=CrumbsTask, name="intelligence.tasks.daily_product_stats_task")
def daily_product_stats_task():
    from intelligence.demand_service import DemandForecastService

    stat_date = timezone.localdate()
    count = DemandForecastService.aggregate_daily_stats(stat_date)
    logger.info("Daily product stats aggregated", extra={"count": count, "date": str(stat_date)})
    return {"products": count, "date": str(stat_date)}


@shared_task(base=CrumbsTask, name="intelligence.tasks.user_behavior_aggregation_task")
def user_behavior_aggregation_task():
    from intelligence.aggregation_service import AggregationService

    affinity = AggregationService.refresh_product_affinity()
    meta = AggregationService.sync_product_intelligence_meta()
    conversions = AggregationService.mark_upsell_conversions()
    return {"affinity_pairs": affinity, "meta_synced": meta, "upsell_conversions": conversions}


@shared_task(base=CrumbsTask, name="intelligence.tasks.demand_forecast_task")
def demand_forecast_task():
    from intelligence.demand_service import DemandForecastService

    forecast_date = timezone.localdate()
    count = DemandForecastService.generate_forecasts(forecast_date, windows=(7, 14))
    return {"forecasts": count, "date": str(forecast_date)}


@shared_task(base=CrumbsTask, name="intelligence.tasks.inventory_optimization_task")
def inventory_optimization_task():
    from intelligence.inventory_optimization_service import InventoryOptimizationService

    count = InventoryOptimizationService.generate_recommendations()
    warnings = len(InventoryOptimizationService.low_stock_warnings())
    overstock = len(InventoryOptimizationService.overstock_risks())
    return {"recommendations": count, "low_stock": warnings, "overstock": overstock}


@shared_task(base=CrumbsTask, name="intelligence.tasks.intelligence_snapshot_task")
def intelligence_snapshot_task():
    from intelligence.insights_service import InsightsService

    snapshot = InsightsService.persist_snapshot()
    return {"report_date": str(snapshot.report_date)}


@shared_task(base=CrumbsTask, name="intelligence.tasks.update_customer_intelligence_task")
def update_customer_intelligence_task():
    from intelligence.customer_intelligence_service import CustomerIntelligenceService

    updated = CustomerIntelligenceService.refresh_all()
    return {"updated": updated}


@shared_task(base=CrumbsTask, name="intelligence.tasks.personalized_sms_offers_task")
def personalized_sms_offers_task():
    from intelligence.personalization_service import PersonalizationService

    sent = PersonalizationService.send_personalized_offers(limit=50)
    return {"sent": sent}
