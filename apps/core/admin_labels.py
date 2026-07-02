"""Persian display labels for Django admin (values unchanged in DB)."""

from delivery.state_machine import STATUS_LABELS_FA
from orders.models import Order
from payments.models import Payment
from products.models import Product

ORDER_PAYMENT_STATUS_FA = {
    Order.PaymentStatus.PENDING_PAYMENT: "در انتظار پرداخت",
    Order.PaymentStatus.PAID: "پرداخت شده",
    Order.PaymentStatus.COD_PENDING: "پرداخت در محل — در انتظار",
    Order.PaymentStatus.COD_CONFIRMED: "پرداخت در محل — تأیید شده",
    Order.PaymentStatus.CASH_RECEIVED: "نقد دریافت شد",
    Order.PaymentStatus.FAILED: "ناموفق",
    Order.PaymentStatus.REFUND_REQUESTED: "درخواست استرداد",
    Order.PaymentStatus.REFUND_PROCESSED: "استرداد انجام شد",
}

ORDER_PAYMENT_METHOD_FA = {
    Order.PaymentMethod.COD: "پرداخت در محل",
    Order.PaymentMethod.ONLINE: "پرداخت آنلاین",
    Order.PaymentMethod.CASH: "نقد در صندوق",
    Order.PaymentMethod.COUNTER_CARD: "کارت در صندوق",
}

FULFILLMENT_TYPE_FA = {
    Order.FulfillmentType.PICKUP: "دریافت در کافه",
    Order.FulfillmentType.COURIER: "پیک (قدیمی)",
    Order.FulfillmentType.EXPRESS: "اکسپرس (قدیمی)",
    Order.FulfillmentType.COD: "پرداخت در محل (قدیمی)",
}

PAYMENT_STATUS_FA = {
    Payment.Status.PENDING: "در انتظار",
    Payment.Status.PROCESSING: "در حال پردازش",
    Payment.Status.SUCCEEDED: "موفق",
    Payment.Status.FAILED: "ناموفق",
    Payment.Status.CANCELLED: "لغو شده",
    Payment.Status.REFUNDED: "استرداد شده",
}

PAYMENT_PROVIDER_FA = {
    Payment.Provider.ZARINPAL: "زرین‌پال",
    Payment.Provider.STRIPE: "استرایپ",
    Payment.Provider.COD: "پرداخت در محل",
    Payment.Provider.CASH: "نقد صندوق",
    Payment.Provider.COUNTER_CARD: "کارت صندوق",
}

PRODUCT_AVAILABILITY_FA = {
    Product.AvailabilityStatus.AVAILABLE: "فعال",
    Product.AvailabilityStatus.OUT_OF_STOCK: "ناموجود",
    Product.AvailabilityStatus.COMING_SOON: "به‌زودی",
}

CAREER_STATUS_FA = {
    "new": "جدید",
    "reviewing": "در حال بررسی",
    "interview": "مصاحبه",
    "rejected": "رد شده",
    "hired": "پذیرفته‌شده",
}


def fa_label(mapping: dict, value: str) -> str:
    return mapping.get(value, value)
