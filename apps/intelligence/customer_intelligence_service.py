"""Customer behavioral intelligence and engagement scoring."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Count, Sum

from growth.models import CouponRedemption, CustomerCLVProfile, GrowthEvent
from growth.services import PAID_PAYMENT_STATUSES
from intelligence.models import CustomerIntelligenceProfile
from orders.models import Order, OrderItem
from products.models import Product

User = get_user_model()

TAG_COOKIE_LOVER = "cookie_lover"
TAG_COFFEE_BUYER = "coffee_buyer"
TAG_DISCOUNT_SENSITIVE = "discount_sensitive"
TAG_VIP_REPEAT = "vip_repeat_buyer"


class CustomerIntelligenceService:
    @classmethod
    def update_user(cls, user) -> CustomerIntelligenceProfile:
        tags = []
        affinity: dict[str, float] = {"cookie": 0.0, "coffee": 0.0, "other": 0.0}
        preferred_ids: list[int] = []

        items = OrderItem.objects.filter(
            order__user=user,
            order__payment_status__in=PAID_PAYMENT_STATUSES,
        ).select_related("product", "product__category", "product__intelligence_meta")

        category_units: dict[str, int] = {}
        product_counts: dict[int, int] = {}

        for item in items:
            product_counts[item.product_id] = product_counts.get(item.product_id, 0) + item.quantity
            meta = getattr(item.product, "intelligence_meta", None)
            if meta and meta.is_cookie:
                key = "cookie"
            elif meta and meta.is_coffee:
                key = "coffee"
            else:
                slug = item.product.category.slug.lower()
                if "cookie" in slug or "کوکی" in item.product.category.name:
                    key = "cookie"
                elif "coffee" in slug or "قهوه" in item.product.category.name:
                    key = "coffee"
                else:
                    key = "other"
            category_units[key] = category_units.get(key, 0) + item.quantity

        total_units = sum(category_units.values()) or 1
        for key, units in category_units.items():
            affinity[key] = round(units / total_units, 3)

        if affinity.get("cookie", 0) >= 0.5:
            tags.append(TAG_COOKIE_LOVER)
        if affinity.get("coffee", 0) >= 0.3:
            tags.append(TAG_COFFEE_BUYER)

        order_count = Order.objects.filter(user=user, payment_status__in=PAID_PAYMENT_STATUSES).count()
        clv = getattr(user, "clv_profile", None)
        if clv and clv.revenue_tier == CustomerCLVProfile.RevenueTier.HIGH and order_count >= 3:
            tags.append(TAG_VIP_REPEAT)

        redemption_count = CouponRedemption.objects.filter(user=user).count()
        discounted_orders = Order.objects.filter(user=user, discount_amount__gt=0).count()
        discount_ratio = discounted_orders / order_count if order_count else 0
        if redemption_count >= 2 or discount_ratio >= 0.5:
            tags.append(TAG_DISCOUNT_SENSITIVE)

        discount_sensitivity = Decimal(str(round(discount_ratio, 2)))

        preferred_ids = [
            pid for pid, _ in sorted(product_counts.items(), key=lambda x: x[1], reverse=True)[:8]
        ]

        since_days = 30
        from datetime import timedelta
        from django.utils import timezone

        since = timezone.now() - timedelta(days=since_days)
        events = GrowthEvent.objects.filter(user=user, created_at__gte=since).count()
        engagement = min(100, events * 5 + order_count * 10)

        profile, _ = CustomerIntelligenceProfile.objects.update_or_create(
            user=user,
            defaults={
                "behavioral_tags": tags,
                "engagement_score": engagement,
                "category_affinity": affinity,
                "discount_sensitivity": discount_sensitivity,
                "preferred_product_ids": preferred_ids,
            },
        )
        return profile

    @classmethod
    def refresh_all(cls) -> int:
        updated = 0
        for user in User.objects.filter(is_active=True):
            cls.update_user(user)
            updated += 1
        return updated

    @classmethod
    def users_with_tag(cls, tag: str, limit: int = 100):
        return User.objects.filter(
            intelligence_profile__behavioral_tags__contains=[tag],
            is_active=True,
        )[:limit]
