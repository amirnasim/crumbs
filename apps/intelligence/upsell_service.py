"""Smart upsell and bundle suggestions at cart/checkout."""

from dataclasses import dataclass

from django.contrib.auth import get_user_model

from intelligence.models import ProductCoPurchase, UpsellImpression
from intelligence.recommendation_service import RecommendationService
from products.models import Product

User = get_user_model()


@dataclass
class UpsellBundle:
    label: str
    products: list[Product]
    bundle_type: str


class UpsellService:
    @classmethod
    def for_cart(cls, cart, *, user=None, limit: int = 4) -> list[Product]:
        cart_product_ids = set(cart.items.values_list("product_id", flat=True))
        if not cart_product_ids:
            return RecommendationService.for_home(user=user, limit=limit)

        suggestions: list[Product] = []
        seen = set(cart_product_ids)

        for item in cart.items.select_related("product", "product__category"):
            pairs = (
                ProductCoPurchase.objects.filter(product=item.product)
                .select_related("related_product", "related_product__category")
                .order_by("-affinity_score")[:5]
            )
            for pair in pairs:
                p = pair.related_product
                if p.pk in seen or not p.is_available:
                    continue
                suggestions.append(p)
                seen.add(p.pk)

        suggestions.extend(
            cls._pairing_fill(cart, exclude_ids=seen, limit=limit - len(suggestions))
        )

        if user and user.is_authenticated and len(suggestions) < limit:
            for p in RecommendationService.for_user(user, limit=limit):
                if p.pk not in seen:
                    suggestions.append(p)
                    seen.add(p.pk)
                if len(suggestions) >= limit:
                    break

        result = suggestions[:limit]
        cls.log_impression(UpsellImpression.Slot.CART, result, user=user, session_key=cart.session_key or "")
        return result

    @classmethod
    def for_checkout(cls, cart, *, user=None, limit: int = 3) -> list[Product]:
        upsells = cls.for_cart(cart, user=user, limit=limit)
        bundles = cls.suggest_bundles(cart)
        for bundle in bundles:
            for p in bundle.products:
                if p.pk not in {u.pk for u in upsells} and p.is_available:
                    upsells.append(p)
                if len(upsells) >= limit:
                    break
        result = upsells[:limit]
        cls.log_impression(UpsellImpression.Slot.CHECKOUT, result, user=user, session_key=cart.session_key or "")
        return result

    @classmethod
    def suggest_bundles(cls, cart) -> list[UpsellBundle]:
        bundles: list[UpsellBundle] = []
        items = list(cart.items.select_related("product", "product__category"))
        if not items:
            return bundles

        has_cookie = any(RecommendationService._is_cookie_product(i.product) for i in items)
        has_coffee = any(
            getattr(getattr(i.product, "intelligence_meta", None), "is_coffee", False)
            or "coffee" in i.product.category.slug.lower()
            or "قهوه" in i.product.category.name
            for i in items
        )

        cart_ids = {i.product_id for i in items}

        if has_cookie and not has_coffee:
            coffee = (
                Product.objects.filter(
                    intelligence_meta__is_coffee=True,
                    availability_status=Product.AvailabilityStatus.AVAILABLE,
                )
                .exclude(pk__in=cart_ids)
                .select_related("category")[:1]
            )
            if coffee:
                bundles.append(
                    UpsellBundle(
                        label="cookie_coffee_combo",
                        products=list(coffee),
                        bundle_type="pairing",
                    )
                )

        cookie_count = sum(i.quantity for i in items if RecommendationService._is_cookie_product(i.product))
        if cookie_count >= 1 and cookie_count < 2:
            extra_cookie = (
                Product.objects.filter(
                    intelligence_meta__is_cookie=True,
                    availability_status=Product.AvailabilityStatus.AVAILABLE,
                )
                .exclude(pk__in=cart_ids)
                .select_related("category")[:1]
            )
            if extra_cookie:
                bundles.append(
                    UpsellBundle(
                        label="buy_2_cookies_suggestion",
                        products=list(extra_cookie),
                        bundle_type="volume",
                    )
                )

        return bundles

    @classmethod
    def _pairing_fill(cls, cart, *, exclude_ids: set, limit: int) -> list[Product]:
        if limit <= 0:
            return []
        items = list(cart.items.select_related("product"))
        has_cookie = any(RecommendationService._is_cookie_product(i.product) for i in items)
        if not has_cookie:
            return list(
                Product.objects.filter(
                    intelligence_meta__is_cookie=True,
                    availability_status=Product.AvailabilityStatus.AVAILABLE,
                )
                .exclude(pk__in=exclude_ids)
                .select_related("category")[:limit]
            )
        return list(
            Product.objects.filter(
                intelligence_meta__is_coffee=True,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
            )
            .exclude(pk__in=exclude_ids)
            .select_related("category")[:limit]
        )

    @classmethod
    def log_impression(cls, slot: str, products: list[Product], *, user=None, session_key: str = ""):
        if not products:
            return
        UpsellImpression.objects.create(
            slot=slot,
            user=user,
            session_key=session_key or "",
            product_ids=[p.pk for p in products],
            metadata={"count": len(products)},
        )
