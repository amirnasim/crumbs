import logging

from celery import shared_task

from core.tasks.base import CrumbsTask
from payments.stale_cleanup import cleanup_stale_online_payments

logger = logging.getLogger("crumbs.tasks")


@shared_task(
    base=CrumbsTask,
    name="payments.tasks.cleanup_stale_online_payments_task",
    autoretry_for=(),
)
def cleanup_stale_online_payments_task():
    """Expire unpaid online checkouts and release reserved stock."""
    logger.info("Stale payment cleanup task starting", extra={"task_name": cleanup_stale_online_payments_task.name})
    result = cleanup_stale_online_payments()
    logger.info("Stale payment cleanup task finished", extra=result)
    return result
