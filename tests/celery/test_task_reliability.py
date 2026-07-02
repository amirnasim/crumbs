"""Celery task reliability — idempotency, retries, beat schedule."""

import pytest
from django.conf import settings

from core.models import BackgroundTaskLog
from core.tasks.dispatch import apply_idempotent_task
from core.tasks.observability import claim_idempotency_key
from orders.tasks import process_order_lifecycle_events


@pytest.mark.celery
@pytest.mark.django_db
class TestCeleryIdempotency:
    def test_claim_idempotency_key_blocks_duplicates(self):
        key = "test:idem:001"
        assert claim_idempotency_key(key, task_name="test.task", task_id=key, payload={}) is True
        assert claim_idempotency_key(key, task_name="test.task", task_id=key, payload={}) is False

    def test_apply_idempotent_task_skips_second_enqueue(self):
        key = "test:idem:002"
        first = apply_idempotent_task(
            process_order_lifecycle_events,
            idempotency_key=key,
            kwargs={"order_id": 1, "events": []},
        )
        second = apply_idempotent_task(
            process_order_lifecycle_events,
            idempotency_key=key,
            kwargs={"order_id": 1, "events": []},
        )
        assert first is not None
        assert second is None
        assert BackgroundTaskLog.objects.filter(idempotency_key=key).count() == 1

    def test_process_order_lifecycle_events_dispatches_sms(self, paid_order, sms_templates):
        events = [
            {
                "kind": "sms_event",
                "event_code": "payment_success",
                "phone": "09121234567",
                "context": {"order_number": paid_order.order_number},
                "user_id": paid_order.user_id,
                "order_id": paid_order.pk,
            }
        ]
        result = process_order_lifecycle_events(paid_order.pk, events)
        assert result["sms"] == 1


@pytest.mark.celery
class TestCeleryBeatSchedule:
    def test_beat_schedule_has_core_jobs(self):
        schedule = settings.CELERY_BEAT_SCHEDULE
        assert "expire-stale-reservations" in schedule
        assert "cleanup-stale-online-payments" in schedule
        assert "retry-failed-sms" in schedule
        assert "daily-sales-analytics" in schedule
