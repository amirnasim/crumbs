import logging

from celery import shared_task

from core.tasks.base import CrumbsTask
from products.services.stock_service import StockService

logger = logging.getLogger("crumbs.tasks")


@shared_task(base=CrumbsTask, name="inventory.tasks.expire_stale_reservations_task")
def expire_stale_reservations_task():
    count = StockService.expire_stale_reservations()
    logger.info("Expired stale stock reservations", extra={"count": count})
    return {"expired": count}
