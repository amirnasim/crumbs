import logging

from celery import shared_task
from django.utils import timezone

from core.models import DailyAnalyticsSnapshot
from core.tasks.base import CrumbsTask
from growth.services import get_analytics_snapshot, process_abandoned_cart_reminders, refresh_customer_segments

logger = logging.getLogger("crumbs.tasks")


@shared_task(base=CrumbsTask, name="growth.tasks.send_abandoned_cart_sms")
def send_abandoned_cart_sms():
    sent = process_abandoned_cart_reminders()
    return {"sent": sent}


@shared_task(base=CrumbsTask, name="growth.tasks.refresh_customer_segments_task")
def refresh_customer_segments_task():
    updated = refresh_customer_segments()
    return {"updated": updated}


@shared_task(base=CrumbsTask, name="growth.tasks.daily_sales_analytics_job")
def daily_sales_analytics_job():
    snapshot = get_analytics_snapshot(days=1)
    report_date = timezone.localdate()
    DailyAnalyticsSnapshot.objects.update_or_create(
        report_date=report_date,
        defaults={"payload": snapshot},
    )
    logger.info("Daily analytics snapshot stored", extra={"report_date": str(report_date)})
    return {"report_date": str(report_date)}


@shared_task(base=CrumbsTask, name="growth.tasks.record_order_analytics_event")
def record_order_analytics_event(order_id: int, event_name: str):
    from orders.models import Order

    order = Order.objects.filter(pk=order_id).only("pk", "total", "status", "payment_status").first()
    if not order:
        return {"skipped": True}
    logger.info(
        "Order analytics event",
        extra={"order_id": order_id, "event": event_name, "total": str(order.total)},
    )
    return {"order_id": order_id, "event": event_name}


@shared_task(base=CrumbsTask, name="growth.tasks.send_promotion_campaign_task")
def send_promotion_campaign_task(campaign_id: int):
    from django.contrib.auth import get_user_model

    from growth.models import PromotionCampaign
    from notifications.dispatch import dispatch_raw_sms

    User = get_user_model()
    campaign = PromotionCampaign.objects.select_related("segment").filter(pk=campaign_id).first()
    if not campaign:
        return {"skipped": True, "reason": "campaign_not_found"}

    if campaign.status == PromotionCampaign.Status.SENT:
        return {"skipped": True, "reason": "already_sent"}

    users = User.objects.filter(is_active=True)
    if campaign.segment_id:
        users = users.filter(segment_memberships__segment=campaign.segment)

    queued = 0
    for user in users.distinct():
        phone = getattr(getattr(user, "profile", None), "phone", "")
        if not phone:
            continue
        dedupe_key = f"promo:{campaign_id}:{user.pk}"
        dispatch_raw_sms(
            phone,
            campaign.message,
            template_code="promotion",
            user=user,
            dedupe_key=dedupe_key,
        )
        queued += 1

    campaign.status = PromotionCampaign.Status.SENT
    campaign.sent_count = queued
    campaign.sent_at = timezone.now()
    campaign.save(update_fields=["status", "sent_count", "sent_at"])
    return {"campaign_id": campaign_id, "queued": queued}


@shared_task(base=CrumbsTask, name="growth.tasks.finalize_growth_order_task")
def finalize_growth_order_task(order_id: int):
    from growth.checkout_integration import GrowthCheckoutFacade
    from orders.models import Order

    order = Order.objects.filter(pk=order_id).first()
    if not order:
        return {"skipped": True}
    result = GrowthCheckoutFacade.finalize_on_payment(order)
    return result


@shared_task(base=CrumbsTask, name="growth.tasks.daily_revenue_snapshot_job")
def daily_revenue_snapshot_job():
    from growth.revenue_analytics import persist_daily_revenue_snapshot

    snapshot = persist_daily_revenue_snapshot()
    return {"report_date": str(snapshot.report_date)}


@shared_task(base=CrumbsTask, name="growth.tasks.funnel_analytics_snapshot_job")
def funnel_analytics_snapshot_job():
    from growth.revenue_analytics import persist_funnel_snapshot

    snapshot = persist_funnel_snapshot()
    return {"report_date": str(snapshot.report_date)}


@shared_task(base=CrumbsTask, name="growth.tasks.refresh_clv_profiles_task")
def refresh_clv_profiles_task():
    from growth.clv_service import CLVService

    updated = CLVService.refresh_all()
    return {"updated": updated}
