"""Flow E: Order event → Celery task → SMS sent → deduplication check."""

import pytest
from django.test import override_settings

from delivery.services import process_checkout
from notifications.models import SMSLog
from orders.models import Order
from tests.factories import CUSTOMER, create_cart_with_item
from tests.mocks.sms import RecordingSMSProvider
from tests.payment_test_settings import STRIPE_ONLINE_SETTINGS


@pytest.mark.integration
@pytest.mark.celery
@pytest.mark.django_db
class TestSMSFlow:
    @override_settings(**STRIPE_ONLINE_SETTINGS, SMS_PROVIDER="kavenegar")
    def test_order_created_sms_and_dedupe(self, user, product, sms_templates, mock_stripe_checkout, mocker):
        provider = RecordingSMSProvider()
        mocker.patch("notifications.services.get_sms_provider", return_value=provider)

        cart = create_cart_with_item(user, product)
        result = process_checkout(cart, CUSTOMER, user=user)
        order = result.order

        sent_logs = SMSLog.objects.filter(order=order, status=SMSLog.Status.SENT)
        assert sent_logs.exists()
        initial_count = sent_logs.count()

        from notifications.services import send_template_sms

        send_template_sms(
            "order_created",
            CUSTOMER["phone"],
            {"order_number": order.order_number, "name": order.first_name, "total": int(order.total)},
            order=order,
            dedupe_key=f"{order.pk}:order_created",
        )
        assert SMSLog.objects.filter(order=order, status=SMSLog.Status.SENT).count() == initial_count

        skipped = SMSLog.objects.filter(order=order, status=SMSLog.Status.SKIPPED).count()
        assert skipped >= 1 or initial_count == 1
