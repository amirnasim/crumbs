"""Event-based revenue attribution for SMS, coupons, referrals, and promotions."""

from decimal import Decimal

from django.db import transaction

from growth.models import AbandonedCartTracker, CouponRedemption, Referral, RevenueAttribution


class AttributionService:
    @classmethod
    @transaction.atomic
    def record_for_order(cls, order) -> list[RevenueAttribution]:
        records = []
        records.extend(cls._attribute_coupon(order))
        records.extend(cls._attribute_referral(order))
        records.extend(cls._attribute_promotion(order))
        records.extend(cls._attribute_sms(order))
        return records

    @classmethod
    def _attribute_coupon(cls, order) -> list[RevenueAttribution]:
        if order.discount_amount <= 0 or not order.coupon_id:
            return []
        redemption = CouponRedemption.objects.filter(order=order).select_related("coupon").first()
        coupon_code = redemption.coupon.code if redemption else (order.coupon.code if order.coupon else "")
        record, _ = RevenueAttribution.objects.get_or_create(
            order=order,
            source_type=RevenueAttribution.SourceType.COUPON,
            source_id=str(order.coupon_id),
            defaults={
                "source_label": coupon_code,
                "attributed_amount": order.discount_amount,
                "metadata": {"coupon_code": coupon_code},
            },
        )
        return [record]

    @classmethod
    def _attribute_referral(cls, order) -> list[RevenueAttribution]:
        if not order.referral_code_applied:
            return []
        referral = Referral.objects.filter(first_order=order).first()
        record, _ = RevenueAttribution.objects.get_or_create(
            order=order,
            source_type=RevenueAttribution.SourceType.REFERRAL,
            source_id=order.referral_code_applied,
            defaults={
                "source_label": order.referral_code_applied,
                "attributed_amount": order.total,
                "metadata": {
                    "referrer_id": referral.referrer_id if referral else None,
                    "referrer_points": referral.referrer_reward_points if referral else 0,
                },
            },
        )
        return [record]

    @classmethod
    def _attribute_promotion(cls, order) -> list[RevenueAttribution]:
        if order.promotion_discount_amount <= 0:
            return []
        rules = (order.notes or "").split("promo:")[-1] if "promo:" in (order.notes or "") else ""
        record, _ = RevenueAttribution.objects.get_or_create(
            order=order,
            source_type=RevenueAttribution.SourceType.PROMOTION,
            source_id=rules[:64] or "promotion",
            defaults={
                "source_label": "Promotion rules",
                "attributed_amount": order.promotion_discount_amount,
            },
        )
        return [record]

    @classmethod
    def _attribute_sms(cls, order) -> list[RevenueAttribution]:
        if not order.user_id:
            return []

        tracker = (
            AbandonedCartTracker.objects.filter(
                recovered_order=order,
                status=AbandonedCartTracker.Status.RECOVERED,
            )
            .order_by("-updated_at")
            .first()
        )
        if tracker is None:
            return []

        record, created = RevenueAttribution.objects.get_or_create(
            order=order,
            source_type=RevenueAttribution.SourceType.SMS,
            source_id=f"abandoned_cart:{tracker.pk}",
            defaults={
                "source_label": f"Abandoned cart SMS (step {tracker.funnel_step})",
                "attributed_amount": order.total,
                "metadata": {
                    "tracker_id": tracker.pk,
                    "reminder_count": tracker.reminder_count,
                    "offered_coupon_id": tracker.offered_coupon_id,
                },
            },
        )
        if created and not tracker.sms_conversion_tracked:
            tracker.sms_conversion_tracked = True
            tracker.save(update_fields=["sms_conversion_tracked", "updated_at"])
            from growth.conversion_service import ConversionService
            from growth.models import GrowthEvent

            ConversionService.track(
                GrowthEvent.EventType.SMS_CONVERSION,
                user=order.user,
                order=order,
                metadata={"tracker_id": tracker.pk, "order_id": order.pk},
            )
        return [record]

    @classmethod
    def coupon_performance(cls, since) -> list[dict]:
        from django.db.models import Count, Sum

        return list(
            RevenueAttribution.objects.filter(
                source_type=RevenueAttribution.SourceType.COUPON,
                created_at__gte=since,
            )
            .values("source_label")
            .annotate(orders=Count("id"), total_discount=Sum("attributed_amount"))
            .order_by("-total_discount")
        )

    @classmethod
    def referral_leaderboard(cls, limit: int = 10) -> list[dict]:
        from django.db.models import Count, Sum

        return list(
            Referral.objects.filter(status=Referral.Status.REWARDED)
            .values("referrer__username", "referrer__first_name", "referrer__last_name")
            .annotate(referrals=Count("id"), points=Sum("referrer_reward_points"))
            .order_by("-referrals")[:limit]
        )
