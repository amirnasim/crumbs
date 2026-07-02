"""Data aggregation pipeline — co-purchase matrix and product meta sync."""

from collections import Counter
from decimal import Decimal

from growth.services import PAID_PAYMENT_STATUSES
from intelligence.models import ProductCoPurchase, ProductIntelligenceMeta, UpsellImpression
from orders.models import Order
from products.models import Product


class AggregationService:
    @classmethod
    def refresh_product_affinity(cls) -> int:
        pairs: Counter = Counter()
        orders = Order.objects.filter(payment_status__in=PAID_PAYMENT_STATUSES).prefetch_related("items")

        for order in orders.iterator(chunk_size=200):
            product_ids = list(order.items.values_list("product_id", flat=True).distinct())
            for i, pid_a in enumerate(product_ids):
                for pid_b in product_ids[i + 1 :]:
                    key = (min(pid_a, pid_b), max(pid_a, pid_b))
                    pairs[key] += 1

        updated = 0
        ProductCoPurchase.objects.all().delete()

        for (pid_a, pid_b), count in pairs.most_common(500):
            if count < 2:
                continue
            score = Decimal(count)
            ProductCoPurchase.objects.create(
                product_id=pid_a,
                related_product_id=pid_b,
                co_count=count,
                affinity_score=score,
            )
            ProductCoPurchase.objects.create(
                product_id=pid_b,
                related_product_id=pid_a,
                co_count=count,
                affinity_score=score,
            )
            updated += 2
        return updated

    @classmethod
    def sync_product_intelligence_meta(cls) -> int:
        count = 0
        for product in Product.objects.select_related("category"):
            slug = product.category.slug.lower()
            name = product.category.name.lower()
            is_cookie = "cookie" in slug or "کوکی" in name
            is_coffee = "coffee" in slug or "قهوه" in name or "coffee" in name
            margin_boost = Decimal("1.20") if product.is_featured else Decimal("1.00")
            if is_cookie:
                margin_boost += Decimal("0.10")

            ProductIntelligenceMeta.objects.update_or_create(
                product=product,
                defaults={
                    "is_cookie": is_cookie,
                    "is_coffee": is_coffee,
                    "margin_boost": margin_boost,
                },
            )
            count += 1
        return count

    @classmethod
    def mark_upsell_conversions(cls) -> int:
        """Link upsell impressions to orders when recommended products were purchased."""
        from django.utils import timezone
        from datetime import timedelta

        from orders.models import OrderItem

        since = timezone.now() - timedelta(days=7)
        impressions = UpsellImpression.objects.filter(created_at__gte=since, converted=False)
        marked = 0

        for imp in impressions.iterator(chunk_size=100):
            if not imp.user_id:
                continue
            order_items = OrderItem.objects.filter(
                order__user_id=imp.user_id,
                order__created_at__gte=imp.created_at,
                order__payment_status__in=PAID_PAYMENT_STATUSES,
                product_id__in=imp.product_ids,
            ).select_related("order").first()
            if order_items:
                imp.converted = True
                imp.conversion_order = order_items.order
                imp.save(update_fields=["converted", "conversion_order"])
                marked += 1
        return marked

