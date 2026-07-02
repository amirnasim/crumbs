"""Rule-based product recommendation engine."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.db.models import Count, Sum

from growth.models import CustomerCLVProfile
from intelligence.models import ProductCoPurchase, ProductIntelligenceMeta
from orders.models import Order, OrderItem
from products.models import Product

User = get_user_model()

PAID_STATUSES = (Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED)


class RecommendationService:
    DEFAULT_LIMIT = 8

    @classmethod
    def for_user(cls, user, *, limit: int | None = None) -> list[Product]:
        limit = limit or cls.DEFAULT_LIMIT
        if not user or not user.is_authenticated:
            return cls._popular_products(limit=limit)

        cache_key = f"crumbs:rec:user:{user.pk}:{limit}"
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        products = cls._score_for_user(user, limit=limit)
        cache.set(cache_key, products, 300)
        return products

    @classmethod
    def for_home(cls, *, user=None, limit: int = 8) -> list[Product]:
        if user and user.is_authenticated:
            recs = cls.for_user(user, limit=limit)
            if len(recs) >= limit // 2:
                return recs
        return cls._popular_products(limit=limit, prefer_cookies=True)

    @classmethod
    def for_product(cls, product: Product, *, user=None, limit: int = 4) -> list[Product]:
        candidates: list[tuple[Decimal, Product]] = []
        seen = {product.pk}

        for cop in (
            ProductCoPurchase.objects.filter(product=product)
            .select_related("related_product", "related_product__category")
            .order_by("-affinity_score")[: limit * 2]
        ):
            p = cop.related_product
            if p.pk in seen or not p.is_available:
                continue
            seen.add(p.pk)
            candidates.append((cop.affinity_score, p))

        if user and user.is_authenticated:
            candidates.extend(cls._personalized_candidates(user, exclude_ids=seen, limit=limit))

        if len(candidates) < limit:
            for p in cls._category_affinity_products(product, exclude_ids=seen, limit=limit):
                if p.pk not in seen:
                    candidates.append((Decimal("1"), p))
                    seen.add(p.pk)

        candidates.sort(key=lambda x: x[0], reverse=True)
        result = [p for _, p in candidates[:limit]]

        if len(result) < limit:
            for p in cls._high_margin_products(exclude_ids=seen, limit=limit - len(result)):
                result.append(p)

        return result[:limit]

    @classmethod
    def _score_for_user(cls, user, *, limit: int) -> list[Product]:
        scores: dict[int, Decimal] = {}
        products_map: dict[int, Product] = {}

        clv = getattr(user, "clv_profile", None)
        intel = getattr(user, "intelligence_profile", None)

        if intel and intel.preferred_product_ids:
            for pid in intel.preferred_product_ids[:10]:
                scores[pid] = scores.get(pid, Decimal("0")) + Decimal("10")

        affinity = (intel.category_affinity if intel else {}) or {}
        cookie_weight = Decimal(str(affinity.get("cookie", 0)))
        coffee_weight = Decimal(str(affinity.get("coffee", 0)))

        order_items = OrderItem.objects.filter(
            order__user=user,
            order__payment_status__in=PAID_STATUSES,
        ).values("product_id").annotate(qty=Sum("quantity"))

        for row in order_items:
            pid = row["product_id"]
            scores[pid] = scores.get(pid, Decimal("0")) + Decimal(row["qty"] or 0) * Decimal("3")

        similar_users = cls._similar_user_ids(user, clv)
        if similar_users:
            similar_items = (
                OrderItem.objects.filter(
                    order__user_id__in=similar_users,
                    order__payment_status__in=PAID_STATUSES,
                )
                .values("product_id")
                .annotate(qty=Sum("quantity"))
                .order_by("-qty")[:20]
            )
            for row in similar_items:
                pid = row["product_id"]
                scores[pid] = scores.get(pid, Decimal("0")) + Decimal("2")

        for pid in list(scores.keys()):
            try:
                product = Product.objects.select_related("category").get(pk=pid)
            except Product.DoesNotExist:
                continue
            if not product.is_available:
                del scores[pid]
                continue
            meta = getattr(product, "intelligence_meta", None)
            boost = meta.margin_boost if meta else Decimal("1")
            if meta and meta.is_cookie:
                boost += cookie_weight * Decimal("0.5")
            if meta and meta.is_coffee:
                boost += coffee_weight * Decimal("0.5")
            if clv and clv.revenue_tier == CustomerCLVProfile.RevenueTier.HIGH:
                boost += Decimal("0.2")
            scores[pid] = scores[pid] * boost
            products_map[pid] = product

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return [products_map[pid] for pid, _ in ranked[:limit]]

    @classmethod
    def _similar_user_ids(cls, user, clv) -> list[int]:
        qs = User.objects.filter(is_active=True).exclude(pk=user.pk)
        if clv:
            qs = qs.filter(clv_profile__revenue_tier=clv.revenue_tier)
        return list(qs.values_list("pk", flat=True)[:25])

    @classmethod
    def _personalized_candidates(cls, user, *, exclude_ids: set, limit: int):
        result = []
        for p in cls._score_for_user(user, limit=limit + len(exclude_ids)):
            if p.pk not in exclude_ids:
                result.append((Decimal("5"), p))
        return result

    @classmethod
    def _popular_products(cls, *, limit: int, prefer_cookies: bool = False) -> list[Product]:
        since_items = (
            OrderItem.objects.filter(order__payment_status__in=PAID_STATUSES)
            .values("product_id")
            .annotate(qty=Sum("quantity"))
            .order_by("-qty")[: limit * 3]
        )
        product_ids = [row["product_id"] for row in since_items]
        if not product_ids:
            qs = Product.objects.filter(availability_status=Product.AvailabilityStatus.AVAILABLE)
            if prefer_cookies:
                qs = qs.select_related("category").order_by("-is_featured", "category__slug", "name")
            else:
                qs = qs.select_related("category").order_by("-is_featured", "-updated_at")
            return list(qs[:limit])

        products = list(
            Product.objects.filter(pk__in=product_ids, availability_status=Product.AvailabilityStatus.AVAILABLE)
            .select_related("category")
        )
        by_id = {p.pk: p for p in products}
        ordered = [by_id[pid] for pid in product_ids if pid in by_id]

        if prefer_cookies:
            cookies = [p for p in ordered if cls._is_cookie_product(p)]
            others = [p for p in ordered if not cls._is_cookie_product(p)]
            ordered = cookies + others

        return ordered[:limit]

    @classmethod
    def _category_affinity_products(cls, product: Product, *, exclude_ids: set, limit: int):
        is_cookie = cls._is_cookie_product(product)
        if is_cookie:
            qs = Product.objects.filter(
                intelligence_meta__is_coffee=True,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
            ).exclude(pk__in=exclude_ids)
        else:
            qs = Product.objects.filter(
                category=product.category,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
            ).exclude(pk__in=exclude_ids)
        return list(qs.select_related("category")[:limit])

    @classmethod
    def _high_margin_products(cls, *, exclude_ids: set, limit: int):
        return list(
            Product.objects.filter(availability_status=Product.AvailabilityStatus.AVAILABLE)
            .exclude(pk__in=exclude_ids)
            .select_related("category", "intelligence_meta")
            .order_by("-intelligence_meta__margin_boost", "-price")[:limit]
        )

    @staticmethod
    def _is_cookie_product(product: Product) -> bool:
        meta = getattr(product, "intelligence_meta", None)
        if meta:
            return meta.is_cookie
        slug = product.category.slug.lower()
        name = product.category.name.lower()
        return "cookie" in slug or "کوکی" in name or "cookie" in name
