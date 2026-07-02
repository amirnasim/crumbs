"""Observability — Sentry, structured logging, and safe operational logs."""

import importlib
import json
import logging
import sys

import pytest

from core.observability import (
    JsonFormatter,
    log_payment_event,
    message_contains_pii,
    scrub_mapping,
    sentry_before_send,
)


def _load_prod_settings(monkeypatch, **env):
    defaults = {
        "SECRET_KEY": "test-production-secret-key-not-for-production-use",
        "DEBUG": "False",
        "LOCAL_PROD_DRY_RUN": "True",
        "SENTRY_DSN": "",
    }
    defaults.update(env)
    for key, value in defaults.items():
        if value is None:
            monkeypatch.delenv(key, raising=False)
        else:
            monkeypatch.setenv(key, value)
    monkeypatch.delenv("SENTRY_RELEASE", raising=False)
    monkeypatch.setenv("SENTRY_RELEASE", env.get("SENTRY_RELEASE", ""))

    monkeypatch.setattr("dotenv.load_dotenv", lambda *args, **kwargs: None)

    for module_name in list(sys.modules):
        if module_name.startswith("config.settings"):
            del sys.modules[module_name]

    return importlib.import_module("config.settings.prod")


def test_prod_settings_imports_without_sentry_dsn(monkeypatch):
    prod = _load_prod_settings(monkeypatch, SENTRY_DSN="")

    assert prod.SENTRY_DSN == ""


def test_prod_settings_initializes_sentry_when_dsn_set(monkeypatch, mocker):
    init_sentry = mocker.patch("core.observability.init_sentry")

    prod = _load_prod_settings(
        monkeypatch,
        SENTRY_DSN="https://example@o0.ingest.sentry.io/0",
        SENTRY_ENVIRONMENT="staging",
        SENTRY_RELEASE="crumbs@test",
    )

    assert prod.SENTRY_DSN
    init_sentry.assert_called_once()
    kwargs = init_sentry.call_args.kwargs
    assert kwargs["dsn"] == "https://example@o0.ingest.sentry.io/0"
    assert kwargs["environment"] == "staging"
    assert kwargs["release"] == "crumbs@test"


def test_sentry_before_send_strips_sensitive_request_data():
    event = {
        "request": {
            "url": "https://crumbs.ir/checkout/",
            "data": {"password": "secret", "phone": "09121234567"},
            "cookies": {"sessionid": "abc"},
            "headers": {"Authorization": "Bearer token", "User-Agent": "curl"},
        },
        "extra": {"email": "user@example.com"},
    }

    cleaned = sentry_before_send(event, {})

    assert "data" not in cleaned["request"]
    assert "cookies" not in cleaned["request"]
    assert "Authorization" not in cleaned["request"]["headers"]
    assert cleaned["extra"]["email"] == "[Filtered]"


def test_scrub_mapping_nested_keys():
    data = {"metadata": {"resume_file": "cv.pdf", "payment_id": 42}}

    cleaned = scrub_mapping(data)

    assert cleaned["metadata"]["resume_file"] == "[Filtered]"
    assert cleaned["metadata"]["payment_id"] == 42


def test_json_formatter_includes_operational_fields():
    record = logging.LogRecord(
        name="crumbs.payments",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg="payment_verified",
        args=(),
        exc_info=None,
    )
    record.order_id = 10
    record.payment_id = 20
    record.provider = "zarinpal"

    payload = json.loads(JsonFormatter().format(record))

    assert payload["order_id"] == 10
    assert payload["payment_id"] == 20
    assert payload["provider"] == "zarinpal"
    assert payload["message"] == "payment_verified"


def test_log_payment_event_avoids_pii_in_message():
    logger = logging.getLogger("crumbs.payments")
    captured: list[logging.LogRecord] = []

    class _CaptureHandler(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            captured.append(record)

    handler = _CaptureHandler()
    logger.addHandler(handler)
    try:
        log_payment_event(
            "payment_callback_received",
            order_id=1,
            payment_id=2,
            provider="zarinpal",
            status="OK",
            request_path="/payments/zarinpal/callback/",
        )
    finally:
        logger.removeHandler(handler)

    assert len(captured) == 1
    formatted = JsonFormatter().format(captured[0])
    assert "0912" not in formatted
    assert "@example.com" not in formatted
    assert not message_contains_pii(formatted)
    assert captured[0].order_id == 1
    assert captured[0].payment_id == 2


@pytest.mark.django_db
def test_stale_cleanup_logs_summary_counts(caplog, user, product):
    from datetime import timedelta

    from django.utils import timezone

    from orders.models import Order
    from payments.models import Payment
    from payments.stale_cleanup import cleanup_stale_online_payments
    from tests.factories import create_order

    caplog.set_level(logging.INFO, logger="payments.stale_cleanup")

    order = create_order(
        user,
        product,
        status=Order.Status.PENDING_PAYMENT,
        payment_status=Order.PaymentStatus.PENDING_PAYMENT,
        payment_method=Order.PaymentMethod.ONLINE,
    )
    payment = Payment.objects.create(
        order=order,
        provider=Payment.Provider.ZARINPAL,
        status=Payment.Status.PENDING,
        amount=order.total,
        currency="irr",
    )
    Payment.objects.filter(pk=payment.pk).update(
        created_at=timezone.now() - timedelta(minutes=45)
    )

    result = cleanup_stale_online_payments()

    assert result["cleaned"] == 1
    assert any("Stale online payment cleanup finished" in r.message for r in caplog.records)
    summary_record = next(r for r in caplog.records if "cleanup finished" in r.message)
    assert summary_record.examined == 1
    assert summary_record.cleaned == 1


@pytest.mark.django_db
def test_stale_cleanup_task_logs_start_and_finish(mocker):
    from payments.tasks import cleanup_stale_online_payments_task

    mocker.patch(
        "payments.tasks.cleanup_stale_online_payments",
        return_value={"examined": 2, "cleaned": 1, "skipped": 1, "errors": 0},
    )
    mock_logger = mocker.patch("payments.tasks.logger")

    result = cleanup_stale_online_payments_task()

    assert result["cleaned"] == 1
    assert mock_logger.info.call_count == 2
    assert "starting" in mock_logger.info.call_args_list[0].args[0]
    assert "finished" in mock_logger.info.call_args_list[1].args[0]
