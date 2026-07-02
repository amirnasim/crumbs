from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone

from notifications.models import SMSLog, SMSTemplate

TRANSACTIONAL_CATEGORIES = {"order", "payment"}
TRANSACTIONAL_EVENTS = {
    "order_created",
    "payment_success",
    "payment_failed",
    "order_confirmed_by_shop",
    "order_preparing",
    "order_out_for_delivery",
    "delivered",
    "order_cancelled",
    "refund_processed",
    "cod_reminder",
}


def _get_template_category(template_code: str) -> str:
    if not template_code:
        return "marketing"
    if template_code in TRANSACTIONAL_EVENTS:
        return "order"
    template = SMSTemplate.objects.filter(code=template_code).only("category").first()
    return template.category if template else "marketing"


def _in_quiet_hours(now: datetime | None = None) -> bool:
    now = now or timezone.localtime()
    start = settings.SMS_QUIET_HOURS_START
    end = settings.SMS_QUIET_HOURS_END
    current = now.time()
    if start < end:
        return start <= current < end
    return current >= start or current < end


def _check_rate_limit(recipient: str, user, template_code: str) -> str | None:
    limit = settings.SMS_RATE_LIMIT_PER_USER_PER_DAY
    if limit <= 0:
        return None

    since = timezone.now() - timedelta(days=1)
    qs = SMSLog.objects.filter(status=SMSLog.Status.SENT, created_at__gte=since)
    if user:
        count = qs.filter(user=user).count()
    else:
        count = qs.filter(recipient=recipient).count()
    if count >= limit:
        return "rate_limit_exceeded"
    return None


def _check_dedupe(
    *,
    recipient: str,
    template_code: str,
    order,
    dedupe_key: str | None,
    metadata: dict,
) -> str | None:
    window = settings.SMS_DEDUPE_WINDOW_SECONDS
    if window <= 0:
        return None

    key = dedupe_key or metadata.get("dedupe_key")
    if not key:
        order_id = getattr(order, "pk", None)
        if order_id:
            key = f"{order_id}:{template_code}"

    if not key:
        return None

    since = timezone.now() - timedelta(seconds=window)
    if SMSLog.objects.filter(
        recipient=recipient,
        template_code=template_code,
        message=metadata.get("_message_preview", ""),
        status__in=[SMSLog.Status.SENT, SMSLog.Status.PENDING],
        created_at__gte=since,
        metadata__dedupe_key=key,
    ).exists():
        return f"dedupe:{key}"

    if order and SMSLog.objects.filter(
        order=order,
        template_code=template_code,
        status=SMSLog.Status.SENT,
    ).exists():
        return f"dedupe:order:{order.pk}:{template_code}"

    return None


def apply_sms_policies(
    *,
    recipient: str,
    template_code: str,
    order=None,
    metadata: dict | None = None,
    force: bool = False,
    dedupe_key: str | None = None,
    user=None,
) -> tuple[bool, str]:
    if force:
        return True, ""

    metadata = metadata or {}
    category = _get_template_category(template_code)

    if _in_quiet_hours() and category not in TRANSACTIONAL_CATEGORIES:
        return False, "quiet_hours"

    if template_code not in TRANSACTIONAL_EVENTS and _in_quiet_hours():
        return False, "quiet_hours"

    if reason := _check_rate_limit(recipient, user, template_code):
        return False, reason

    if reason := _check_dedupe(
        recipient=recipient,
        template_code=template_code,
        order=order,
        dedupe_key=dedupe_key,
        metadata=metadata,
    ):
        return False, reason

    return True, ""
