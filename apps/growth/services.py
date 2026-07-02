from datetime import timedelta
from decimal import Decimal

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db.models import Count, Max, Sum
from django.utils import timezone

from cart.models import Cart
from growth.models import AbandonedCartTracker, CustomerSegment, CustomerSegmentMembership
from loyalty.models import LoyaltyAccount
from orders.models import Order
from notifications.dispatch import dispatch_template_sms

User = get_user_model()


def resolve_phone_for_cart(cart: Cart) -> str:
    if cart.user_id:
        profile_phone = getattr(getattr(cart.user, "profile", None), "phone", "")
        if profile_phone:
            return profile_phone
        latest_order = (
            Order.objects.filter(user=cart.user).exclude(phone="").order_by("-created_at").first()
        )
        if latest_order and latest_order.phone:
            return latest_order.phone
    return ""


def sync_abandoned_cart_tracker(cart: Cart) -> AbandonedCartTracker | None:
    if cart.is_empty:
        AbandonedCartTracker.objects.filter(cart=cart, status=AbandonedCartTracker.Status.ACTIVE).update(
            status=AbandonedCartTracker.Status.EXPIRED
        )
        return None

    phone = resolve_phone_for_cart(cart)
    tracker, _ = AbandonedCartTracker.objects.update_or_create(
        cart=cart,
        defaults={
            "user": cart.user,
            "phone": phone,
            "session_key": cart.session_key or "",
            "item_count": cart.total_items,
            "subtotal": cart.get_subtotal(),
            "last_activity_at": timezone.now(),
            "status": AbandonedCartTracker.Status.ACTIVE,
        },
    )
    return tracker


def mark_abandoned_cart_recovered(order: Order) -> None:
    if not order.user_id:
        return
    try:
        cart = Cart.objects.get(user=order.user)
    except Cart.DoesNotExist:
        return

    AbandonedCartTracker.objects.filter(cart=cart).update(
        status=AbandonedCartTracker.Status.RECOVERED,
        recovered_order=order,
    )


def process_abandoned_cart_reminders() -> int:
    now = timezone.now()
    step1_hours = settings.ABANDONED_CART_HOURS
    step2_hours = getattr(settings, "ABANDONED_CART_STEP2_HOURS", 24)
    high_value_threshold = Decimal(str(getattr(settings, "ABANDONED_CART_HIGH_VALUE_THRESHOLD", 500000)))
    max_reminders = getattr(settings, "ABANDONED_CART_MAX_REMINDERS", 3)
    sent = 0

    trackers = (
        AbandonedCartTracker.objects.filter(
            status__in=[AbandonedCartTracker.Status.ACTIVE, AbandonedCartTracker.Status.REMINDED],
            reminder_count__lt=max_reminders,
        )
        .exclude(phone="")
        .select_related("cart", "user", "offered_coupon")
    )

    for tracker in trackers:
        if tracker.cart.is_empty:
            tracker.status = AbandonedCartTracker.Status.EXPIRED
            tracker.save(update_fields=["status", "updated_at"])
            continue

        hours_idle = (now - tracker.last_activity_at).total_seconds() / 3600
        step = tracker.funnel_step

        if step == 0 and hours_idle < step1_hours:
            continue
        if step == 1 and hours_idle < step2_hours:
            continue
        if step >= 2 and hours_idle < step2_hours:
            continue

        template_code = "abandoned_cart"
        context = {
            "name": tracker.user.first_name if tracker.user_id else "مشتری",
            "item_count": tracker.item_count,
            "subtotal": int(tracker.subtotal),
            "shop_url": settings.SITE_URL,
        }

        if step == 0:
            tracker.funnel_step = 1
        elif step == 1:
            template_code = "abandoned_cart_step2"
            tracker.funnel_step = 2
        elif step >= 2 and tracker.subtotal >= high_value_threshold:
            from growth.models import Coupon

            coupon = tracker.offered_coupon
            if coupon is None:
                coupon = Coupon.objects.filter(
                    campaign_type=Coupon.CampaignType.ABANDONED_CART,
                    is_active=True,
                ).first()
                if coupon:
                    tracker.offered_coupon = coupon
                    if tracker.user_id:
                        tracker.cart.applied_coupon_code = coupon.code
                        tracker.cart.save(update_fields=["applied_coupon_code", "updated_at"])
            if coupon:
                template_code = "abandoned_cart_discount"
                context["coupon_code"] = coupon.code
                context["discount"] = int(coupon.discount_value)
            tracker.funnel_step = 3

        dedupe_key = f"abandoned:{tracker.pk}:{tracker.reminder_count + 1}"
        dispatch_template_sms(
            template_code,
            tracker.phone,
            context,
            user=tracker.user,
            metadata={"tracker_id": tracker.pk, "funnel_step": tracker.funnel_step},
            dedupe_key=dedupe_key,
        )

        from growth.conversion_service import ConversionService
        from growth.models import GrowthEvent

        ConversionService.track(
            GrowthEvent.EventType.SMS_SENT,
            user=tracker.user,
            cart=tracker.cart,
            metadata={"tracker_id": tracker.pk, "template": template_code},
        )

        tracker.reminder_count += 1
        tracker.last_reminder_at = now
        tracker.status = AbandonedCartTracker.Status.REMINDED
        tracker.save(
            update_fields=[
                "reminder_count",
                "last_reminder_at",
                "status",
                "funnel_step",
                "offered_coupon",
                "updated_at",
            ]
        )
        sent += 1

    return sent


PAID_PAYMENT_STATUSES = (
    Order.PaymentStatus.PAID,
    Order.PaymentStatus.CASH_RECEIVED,
)


def classify_user_segment(user) -> str:
    now = timezone.now()
    orders = Order.objects.filter(user=user, payment_status__in=PAID_PAYMENT_STATUSES)
    order_count = orders.count()
    last_order_at = orders.aggregate(last=Max("created_at"))["last"]
    lifetime_spend = orders.aggregate(total=Sum("total"))["total"] or Decimal("0")

    loyalty = LoyaltyAccount.objects.filter(user=user).first()
    tier = loyalty.tier if loyalty else LoyaltyAccount.Tier.NORMAL

    if order_count == 0:
        return CustomerSegment.Code.NEW
    if tier == LoyaltyAccount.Tier.GOLD or lifetime_spend >= Decimal("5000000"):
        return CustomerSegment.Code.VIP
    if last_order_at and (now - last_order_at).days > 90:
        return CustomerSegment.Code.DORMANT
    if last_order_at and (now - last_order_at).days > 45:
        return CustomerSegment.Code.AT_RISK
    return CustomerSegment.Code.ACTIVE


def refresh_customer_segments() -> int:
    segments = {s.code: s for s in CustomerSegment.objects.filter(is_active=True)}
    updated = 0

    for user in User.objects.filter(is_active=True):
        code = classify_user_segment(user)
        segment = segments.get(code)
        if segment is None:
            continue

        current = CustomerSegmentMembership.objects.filter(user=user).first()
        if current and current.segment_id == segment.pk:
            continue

        CustomerSegmentMembership.objects.filter(user=user).delete()
        CustomerSegmentMembership.objects.create(user=user, segment=segment)
        updated += 1

    return updated


def send_promotion_campaign(campaign) -> int:
    """Queue promotional SMS via Celery (admin action entry point)."""
    from growth.tasks import send_promotion_campaign_task

    send_promotion_campaign_task.delay(campaign.pk)
    return 0


def get_analytics_snapshot(days: int = 30) -> dict:
    since = timezone.now() - timedelta(days=days)
    paid_orders = Order.objects.filter(
        payment_status__in=PAID_PAYMENT_STATUSES,
        created_at__gte=since,
    )
    revenue = paid_orders.aggregate(total=Sum("total"))["total"] or Decimal("0")
    order_count = paid_orders.count()

    from orders.models import OrderItem

    top_products = (
        OrderItem.objects.filter(
            order__payment_status__in=PAID_PAYMENT_STATUSES,
            order__created_at__gte=since,
        )
        .values("product_name")
        .annotate(qty=Sum("quantity"), revenue=Sum("line_total"))
        .order_by("-revenue")[:10]
    )

    top_customers = (
        paid_orders.filter(user__isnull=False)
        .values("user__username", "user__email", "user__first_name", "user__last_name")
        .annotate(orders=Count("id"), spent=Sum("total"))
        .order_by("-spent")[:10]
    )

    from notifications.models import SMSLog

    sms_sent = SMSLog.objects.filter(status=SMSLog.Status.SENT, created_at__gte=since).count()
    sms_failed = SMSLog.objects.filter(status=SMSLog.Status.FAILED, created_at__gte=since).count()
    abandoned_active = AbandonedCartTracker.objects.filter(
        status__in=[AbandonedCartTracker.Status.ACTIVE, AbandonedCartTracker.Status.REMINDED]
    ).count()
    abandoned_recovered = AbandonedCartTracker.objects.filter(
        status=AbandonedCartTracker.Status.RECOVERED,
        updated_at__gte=since,
    ).count()

    segment_counts = (
        CustomerSegmentMembership.objects.values("segment__name")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    loyalty_counts = (
        LoyaltyAccount.objects.values("tier")
        .annotate(count=Count("id"))
        .order_by("tier")
    )

    return {
        "days": days,
        "revenue": revenue,
        "order_count": order_count,
        "avg_order_value": revenue / order_count if order_count else Decimal("0"),
        "top_products": list(top_products),
        "top_customers": list(top_customers),
        "sms_sent": sms_sent,
        "sms_failed": sms_failed,
        "abandoned_active": abandoned_active,
        "abandoned_recovered": abandoned_recovered,
        "segment_counts": list(segment_counts),
        "loyalty_counts": list(loyalty_counts),
    }
