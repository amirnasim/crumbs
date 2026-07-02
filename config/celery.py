"""Celery application for CRUMBS background processing."""

import os

from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.prod")

app = Celery("crumbs")
app.config_from_object("django.conf:settings", namespace="CELERY")


def _register_task_modules():
    import django
    from django.apps import apps

    if not apps.ready:
        django.setup()

    import notifications.tasks  # noqa: F401
    import growth.tasks  # noqa: F401
    import orders.tasks  # noqa: F401
    import payments.tasks  # noqa: F401
    import loyalty.tasks  # noqa: F401
    import inventory.tasks  # noqa: F401
    import intelligence.tasks  # noqa: F401


_register_task_modules()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
