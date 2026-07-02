"""Inventory optimization based on demand forecasts and capacity."""

from datetime import timedelta
from decimal import Decimal

from django.utils import timezone

from intelligence.demand_service import DemandForecastService
from intelligence.models import ProductBakeRecommendation, ProductDemandForecast
from inventory.models import DailyProductionCapacity, ProductInventory
from products.models import Product


class InventoryOptimizationService:
    SAFETY_STOCK_RATIO = Decimal("0.15")
    OVERSTOCK_RATIO = Decimal("1.50")

    @classmethod
    def generate_recommendations(cls, recommendation_date=None) -> int:
        recommendation_date = recommendation_date or timezone.localdate()
        count = 0

        for product in Product.objects.filter(availability_status=Product.AvailabilityStatus.AVAILABLE):
            rec = cls._recommend_for_product(product, recommendation_date)
            if rec is None:
                continue
            ProductBakeRecommendation.objects.update_or_create(
                product=product,
                recommendation_date=recommendation_date,
                defaults=rec,
            )
            count += 1
        return count

    @classmethod
    def _recommend_for_product(cls, product, recommendation_date) -> dict | None:
        forecast = (
            ProductDemandForecast.objects.filter(
                product=product,
                forecast_for_date=recommendation_date,
                window_days=7,
            )
            .first()
        )
        if forecast is None:
            DemandForecastService.generate_forecasts(recommendation_date, windows=(7,))
            forecast = ProductDemandForecast.objects.filter(
                product=product,
                forecast_for_date=recommendation_date,
                window_days=7,
            ).first()

        predicted = int(forecast.predicted_units) if forecast else 0
        if predicted <= 0:
            predicted = 5

        inventory = ProductInventory.objects.filter(product=product).first()
        current_stock = inventory.available_quantity if inventory else 0

        capacity = DailyProductionCapacity.objects.filter(
            product=product,
            production_date=recommendation_date,
        ).first()
        capacity_available = capacity.available_units if capacity else 999

        safety = int(predicted * cls.SAFETY_STOCK_RATIO) + 1
        suggested = max(0, predicted + safety - current_stock)
        suggested = min(suggested, capacity_available if capacity else suggested)

        status = ProductBakeRecommendation.Status.OK
        notes = ""
        low_threshold = inventory.low_stock_threshold if inventory else 5

        if current_stock <= low_threshold:
            status = ProductBakeRecommendation.Status.LOW_STOCK
            notes = f"Current stock ({current_stock}) at or below threshold ({low_threshold})."
        elif current_stock > predicted * cls.OVERSTOCK_RATIO and predicted > 0:
            status = ProductBakeRecommendation.Status.OVERSTOCK_RISK
            notes = f"Stock ({current_stock}) exceeds forecast ({predicted}) by >50%."

        return {
            "suggested_bake_qty": suggested,
            "forecast_demand": Decimal(predicted),
            "current_stock": current_stock,
            "capacity_available": capacity_available if capacity else 0,
            "status": status,
            "notes": notes,
        }

    @classmethod
    def low_stock_warnings(cls) -> list[ProductBakeRecommendation]:
        today = timezone.localdate()
        return list(
            ProductBakeRecommendation.objects.filter(
                recommendation_date=today,
                status=ProductBakeRecommendation.Status.LOW_STOCK,
            ).select_related("product")[:50]
        )

    @classmethod
    def overstock_risks(cls) -> list[ProductBakeRecommendation]:
        today = timezone.localdate()
        return list(
            ProductBakeRecommendation.objects.filter(
                recommendation_date=today,
                status=ProductBakeRecommendation.Status.OVERSTOCK_RISK,
            ).select_related("product")[:50]
        )
