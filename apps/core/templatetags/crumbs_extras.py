from decimal import Decimal, ROUND_HALF_UP

from django import template

register = template.Library()

PERSIAN_DIGITS = str.maketrans("0123456789", "۰۱۲۳۴۵۶۷۸۹")

AVAILABILITY_FA = {
    "available": "موجود",
    "out_of_stock": "ناموجود",
    "coming_soon": "به‌زودی",
}


@register.filter
def fa_num(value):
    """Convert Western digits to Persian digits."""
    return str(value).translate(PERSIAN_DIGITS)


@register.filter
def toman(value):
    """Format a numeric value as Persian Toman (display only)."""
    amount = Decimal(value).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    formatted = f"{int(amount):,}".replace(",", "،")
    return f"{formatted.translate(PERSIAN_DIGITS)} تومان"


ORDER_STATUS_FA = {
    "pending_payment": "در انتظار پرداخت آنلاین",
    "awaiting_payment": "در انتظار پرداخت در صندوق",
    "paid": "پرداخت شده",
    "confirmed_by_shop": "تأیید فروشگاه",
    "preparing": "در حال آماده‌سازی",
    "packaged": "آماده تحویل از کانتر",
    "out_for_delivery": "آماده تحویل از کانتر",
    "delivered": "تحویل شد",
    "cancelled": "لغو شد",
    "refunded": "استرداد شد",
    "pending": "در انتظار",
    "confirmed": "تأیید شده",
    "processing": "در حال آماده‌سازی",
    "ready": "آماده تحویل از کانتر",
    "completed": "تحویل شد",
}


PAYMENT_METHOD_FA = {
    "online": "پرداخت آنلاین",
    "cash": "پرداخت نقدی در صندوق",
    "counter_card": "پرداخت با کارت در صندوق",
    "cod": "پرداخت در محل (قدیمی)",
}

FULFILLMENT_TYPE_FA = {
    "pickup": "تحویل از کانتر",
    "courier": "پیک (قدیمی)",
    "express": "ارسال سریع (قدیمی)",
    "cod": "COD (قدیمی)",
}

PAYMENT_STATUS_FA = {
    "pending_payment": "در انتظار پرداخت",
    "paid": "پرداخت شده",
    "cod_pending": "در انتظار تأیید",
    "cod_confirmed": "تأیید شده",
    "cash_received": "دریافت شد",
    "failed": "ناموفق",
    "refund_requested": "درخواست استرداد",
    "refund_processed": "استرداد شد",
    "not_required": "نیاز نیست",
    "pending": "در انتظار پرداخت",
    "refunded": "بازگشت وجه",
}


@register.filter
def fa_payment_status(order):
    return PAYMENT_STATUS_FA.get(order.payment_status, order.get_payment_status_display())


@register.filter
def fa_payment_method(order):
    return PAYMENT_METHOD_FA.get(order.payment_method, order.get_payment_method_display())


@register.filter
def fa_fulfillment_type(order):
    if order.is_in_cafe_pickup_order:
        return "تحویل از کانتر"
    return FULFILLMENT_TYPE_FA.get(order.delivery_type, order.get_fulfillment_type_display())


@register.filter
def order_display_number(order):
    if getattr(order, "daily_sequence", None):
        return f"#{order.daily_sequence}"
    return ""


@register.filter
def fa_order_status(order):
    return ORDER_STATUS_FA.get(order.status, order.get_status_display())


@register.simple_tag
def order_status_timeline(order):
    from orders.customer_status import build_order_status_timeline

    return build_order_status_timeline(order)


@register.filter
def fa_payment_record_status(payment):
    status_map = {
        "pending": "در انتظار",
        "processing": "در حال پردازش",
        "succeeded": "موفق",
        "failed": "ناموفق",
        "cancelled": "لغو شده",
        "refunded": "بازگشت وجه",
    }
    return status_map.get(payment.status, payment.get_status_display())


@register.filter
def fa_availability(product):
    """Persian label for product availability status."""
    return AVAILABILITY_FA.get(
        product.availability_status,
        product.get_availability_status_display(),
    )


def _normalize_product_id(value):
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_wishlist_product_ids(wishlist_product_ids):
    if wishlist_product_ids is None:
        return set()

    if isinstance(wishlist_product_ids, str):
        if not wishlist_product_ids.strip():
            return set()
        parts = wishlist_product_ids.split(",")
        return {
            product_id
            for part in parts
            if (product_id := _normalize_product_id(part.strip())) is not None
        }

    if isinstance(wishlist_product_ids, (list, tuple, set, frozenset)):
        normalized = set()
        for item in wishlist_product_ids:
            product_id = _normalize_product_id(item)
            if product_id is not None:
                normalized.add(product_id)
        return normalized

    if hasattr(wishlist_product_ids, "__iter__") and not isinstance(wishlist_product_ids, (bytes, bytearray)):
        normalized = set()
        for item in wishlist_product_ids:
            product_id = _normalize_product_id(item)
            if product_id is not None:
                normalized.add(product_id)
        return normalized

    product_id = _normalize_product_id(wishlist_product_ids)
    return {product_id} if product_id is not None else set()


@register.simple_tag
def in_wishlist(wishlist_product_ids, product_id):
    normalized_product_id = _normalize_product_id(product_id)
    if normalized_product_id is None:
        return False
    return normalized_product_id in _normalize_wishlist_product_ids(wishlist_product_ids)
