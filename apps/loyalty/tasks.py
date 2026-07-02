import logging

from celery import shared_task

from core.tasks.base import CrumbsTask
from loyalty.services import award_points_for_order
from orders.models import Order

logger = logging.getLogger("crumbs.tasks")


@shared_task(base=CrumbsTask, bind=True, name="loyalty.tasks.award_loyalty_points_task")
def award_loyalty_points_task(self, order_id: int):
    order = Order.objects.select_related("user").filter(pk=order_id).first()
    if not order:
        return {"skipped": True, "reason": "order_not_found"}

    account = award_points_for_order(order)
    if account is None:
        return {"skipped": True, "reason": "not_eligible"}

    return {"order_id": order_id, "points": account.points, "tier": account.tier}
