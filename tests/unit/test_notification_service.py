"""Unit tests for unified order notification infrastructure."""

import pytest
from django.core import mail

from notifications.models import SMSLog
from notifications.notification_service import NotificationService
from notifications.services import SMSService
from orders.events import emit_order_lifecycle_events
from orders.models import Order
from orders.services.order_service import OrderService
from orders.tasks import process_order_lifecycle_events
from tests.factories import create_order, create_product, create_user
from tests.mocks.sms import RecordingSMSProvider


@pytest.fixture
def notification_context(order):
    return {
        "name": order.first_name,
        "order_number": order.order_number,
        "total": int(order.total),
    }


@pytest.fixture
def order(db, user, product, mocker):
    mocker.patch("orders.events.emit_order_lifecycle_events")
    return create_order(
        user,
        product,
        status=Order.Status.CONFIRMED_BY_SHOP,
        payment_status=Order.PaymentStatus.COD_PENDING,
        payment_method=Order.PaymentMethod.COD,
    )


@pytest.mark.django_db
class TestNotificationService:
    def test_order_created_notification_sent(self, order, sms_templates, mocker, notification_context):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)
        mail.outbox.clear()

        result = NotificationService.notify_order_created(
            order,
            phone=order.phone,
            context=notification_context,
        )

        assert result["sms_log_id"] is not None
        assert result["email_sent"] is True
        assert SMSLog.objects.filter(order=order, template_code="order_created", status=SMSLog.Status.SENT).exists()
        assert len(mail.outbox) == 1
        assert order.order_number in mail.outbox[0].subject
        assert len(provider.messages) == 1

    def test_status_update_notification_sent(self, order, sms_templates, mocker, notification_context):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)
        mail.outbox.clear()
        notification_context["status"] = "در حال آماده‌سازی"

        result = NotificationService.notify_order_status_updated(
            order,
            phone=order.phone,
            context=notification_context,
            event_code="order_preparing",
        )

        assert result["sms_log_id"] is not None
        assert result["email_sent"] is True
        assert SMSLog.objects.filter(order=order, template_code="order_preparing").exists()
        assert len(mail.outbox) == 1

    def test_payment_received_notification_sent(self, order, sms_templates, mocker, notification_context):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)
        mail.outbox.clear()
        order.payment_status = Order.PaymentStatus.CASH_RECEIVED
        order.save(update_fields=["payment_status", "updated_at"])

        result = NotificationService.notify_payment_received(
            order,
            phone=order.phone,
            context=notification_context,
        )

        assert result["sms_log_id"] is not None
        assert result["email_sent"] is True
        assert SMSLog.objects.filter(order=order, template_code="payment_success").exists()
        assert "Payment received" in mail.outbox[0].subject

    def test_sms_mock_provider_is_called(self, order, sms_templates, mocker, notification_context):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)

        NotificationService.notify_order_created(
            order,
            phone=order.phone,
            context=notification_context,
        )

        assert provider.messages == [(order.phone, provider.messages[0][1])]

    def test_notification_failure_is_logged_but_does_not_raise(
        self, order, sms_templates, mocker, notification_context, caplog
    ):
        mocker.patch.object(
            SMSService,
            "send_event",
            side_effect=RuntimeError("sms gateway down"),
        )
        mocker.patch(
            "notifications.email_service.EmailService.send_order_event",
            side_effect=RuntimeError("smtp down"),
        )

        with caplog.at_level("ERROR"):
            result = NotificationService.notify_order_created(
                order,
                phone=order.phone,
                context=notification_context,
            )

        assert "sms:" in result["errors"][0]
        assert any("email:" in error for error in result["errors"])
        assert any("SMS notification failed" in record.message for record in caplog.records)
        assert any("Email notification failed" in record.message for record in caplog.records)

    def test_lifecycle_task_continues_when_notification_handler_errors(
        self, order, sms_templates, mocker, notification_context
    ):
        mocker.patch(
            "notifications.notification_service.NotificationService.notify_order_event",
            side_effect=RuntimeError("notification crashed"),
        )

        events = [
            {
                "kind": "sms_event",
                "event_code": "order_created",
                "phone": order.phone,
                "context": notification_context,
                "user_id": order.user_id,
                "order_id": order.pk,
            },
            {
                "kind": "analytics_touch",
                "order_id": order.pk,
                "event": "payment_success",
            },
        ]
        analytics = mocker.patch("growth.tasks.record_order_analytics_event.apply_async")

        result = process_order_lifecycle_events(order.pk, events)

        assert result["sms"] == 0
        analytics.assert_called_once()

    def test_emit_order_lifecycle_events_does_not_break_order_save(self, user, product, mocker):
        mocker.patch(
            "core.tasks.dispatch.apply_idempotent_task",
            side_effect=RuntimeError("broker unavailable"),
        )

        order = create_order(
            user,
            product,
            status=Order.Status.CONFIRMED_BY_SHOP,
            payment_status=Order.PaymentStatus.COD_PENDING,
            payment_method=Order.PaymentMethod.COD,
        )

        emit_order_lifecycle_events(
            order,
            created=False,
            prev_payment=Order.PaymentStatus.COD_PENDING,
            prev_status=Order.Status.CONFIRMED_BY_SHOP,
        )
        OrderService.transition(order, Order.Status.PREPARING)

        order.refresh_from_db()
        assert order.status == Order.Status.PREPARING

    def test_process_order_lifecycle_sends_sms_and_email(self, order, sms_templates, mocker, notification_context):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)
        mail.outbox.clear()

        events = [
            {
                "kind": "sms_event",
                "event_code": "order_preparing",
                "phone": order.phone,
                "context": {**notification_context, "status": "در حال آماده‌سازی"},
                "user_id": order.user_id,
                "order_id": order.pk,
            }
        ]

        result = process_order_lifecycle_events(order.pk, events)

        assert result["sms"] == 1
        assert result["email"] == 1
        assert len(provider.messages) == 1
        assert len(mail.outbox) == 1
