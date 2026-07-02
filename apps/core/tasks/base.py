import logging

from celery import Task

from core.observability import OPS_LOG_FIELDS
from core.tasks.observability import (
    mark_task_failure,
    mark_task_retry,
    mark_task_started,
    mark_task_success,
)

logger = logging.getLogger("crumbs.tasks")


class CrumbsTask(Task):
    """Base task with exponential backoff, structured logs, and dead-letter tracking."""

    autoretry_for = (Exception,)
    retry_backoff = True
    retry_backoff_max = 600
    retry_jitter = True
    max_retries = 5
    acks_late = True

    def before_start(self, task_id, args, kwargs):
        mark_task_started(task_id, task_name=self.name)
        logger.info(
            "Task starting",
            extra={"task_id": task_id, "task_name": self.name, "kwargs_keys": list(kwargs.keys())},
        )

    def on_success(self, retval, task_id, args, kwargs):
        mark_task_success(
            task_id,
            result=retval if isinstance(retval, (dict, list, str, int, float, bool)) else None,
            task_name=self.name,
        )
        extra = {"task_id": task_id, "task_name": self.name}
        if isinstance(retval, dict):
            for key, value in retval.items():
                if key in OPS_LOG_FIELDS:
                    extra[key] = value
        logger.info("Task succeeded", extra=extra)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        retries = self.request.retries if self.request else 0
        dead = retries >= self.max_retries
        mark_task_failure(task_id, error=str(exc), retry_count=retries, dead=dead, task_name=self.name)
        logger.exception(
            "Task failed",
            extra={"task_id": task_id, "task_name": self.name, "retries": retries, "dead_letter": dead},
        )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        retries = self.request.retries if self.request else 0
        mark_task_retry(task_id, retry_count=retries, error=str(exc), task_name=self.name)
        logger.warning(
            "Task retry scheduled",
            extra={"task_id": task_id, "task_name": self.name, "retries": retries},
        )
