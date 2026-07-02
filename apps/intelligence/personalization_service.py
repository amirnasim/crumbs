"""Personalized SMS offers via existing notification dispatch."""

import logging

from django.conf import settings

from intelligence.customer_intelligence_service import (
    TAG_COOKIE_LOVER,
    TAG_DISCOUNT_SENSITIVE,
    TAG_VIP_REPEAT,
    CustomerIntelligenceService,
)
from intelligence.models import UpsellImpression
from intelligence.recommendation_service import RecommendationService
from notifications.dispatch import dispatch_template_sms
from products.models import Product

logger = logging.getLogger("crumbs.tasks")


class PersonalizationService:
    TEMPLATE_COOKIE = "intel_cookie_offer"
    TEMPLATE_VIP = "intel_vip_offer"

    @classmethod
    def send_personalized_offers(cls, *, limit: int = 50) -> int:
        sent = 0

        vip_users = CustomerIntelligenceService.users_with_tag(TAG_VIP_REPEAT, limit=limit // 2)
        for user in vip_users:
            if cls._send_vip_offer(user):
                sent += 1

        cookie_users = CustomerIntelligenceService.users_with_tag(TAG_COOKIE_LOVER, limit=limit // 2)
        for user in cookie_users:
            if user in vip_users:
                continue
            if cls._send_cookie_offer(user):
                sent += 1

        return sent

    @classmethod
    def _send_vip_offer(cls, user) -> bool:
        phone = getattr(getattr(user, "profile", None), "phone", "")
        if not phone:
            return False

        recs = RecommendationService.for_user(user, limit=1)
        product = recs[0] if recs else None
        dedupe_key = f"intel:vip:{user.pk}:{timezone_date()}"

        dispatch_template_sms(
            cls.TEMPLATE_VIP,
            phone,
            {
                "name": user.first_name or "مشتری",
                "product_name": product.name if product else "محصول ویژه",
                "shop_url": settings.SITE_URL,
            },
            user=user,
            dedupe_key=dedupe_key,
        )
        cls._log_sms_impression(user, recs[:1])
        return True

    @classmethod
    def _send_cookie_offer(cls, user) -> bool:
        phone = getattr(getattr(user, "profile", None), "phone", "")
        if not phone:
            return False

        intel = getattr(user, "intelligence_profile", None)
        if intel and TAG_DISCOUNT_SENSITIVE in (intel.behavioral_tags or []):
            return False

        new_cookie = (
            Product.objects.filter(
                intelligence_meta__is_cookie=True,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
                is_featured=True,
            )
            .exclude(pk__in=intel.preferred_product_ids if intel else [])
            .first()
        )
        if not new_cookie:
            new_cookie = Product.objects.filter(
                intelligence_meta__is_cookie=True,
                availability_status=Product.AvailabilityStatus.AVAILABLE,
            ).first()

        if not new_cookie:
            return False

        dedupe_key = f"intel:cookie:{user.pk}:{new_cookie.pk}:{timezone_date()}"
        dispatch_template_sms(
            cls.TEMPLATE_COOKIE,
            phone,
            {
                "name": user.first_name or "مشتری",
                "product_name": new_cookie.name,
                "shop_url": settings.SITE_URL + new_cookie.get_absolute_url(),
            },
            user=user,
            dedupe_key=dedupe_key,
        )
        cls._log_sms_impression(user, [new_cookie])
        return True

    @staticmethod
    def _log_sms_impression(user, products: list[Product]):
        UpsellImpression.objects.create(
            slot=UpsellImpression.Slot.SMS,
            user=user,
            product_ids=[p.pk for p in products],
            metadata={"channel": "personalized_sms"},
        )


def timezone_date():
    from django.utils import timezone

    return timezone.localdate().isoformat()
