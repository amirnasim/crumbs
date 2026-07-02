from django.core.management.base import BaseCommand

from growth.models import Coupon, CustomerSegment, PromotionRule
from notifications.models import SMSTemplate


DEFAULT_SEGMENTS = [
    ("new", "جدید", "مشتریان بدون سفارش پرداخت‌شده"),
    ("active", "فعال", "مشتریان با خرید اخیر"),
    ("vip", "VIP", "مشتریان طلایی یا با خرید بالا"),
    ("at_risk", "در معرض ریزش", "بدون خرید در ۴۵ روز گذشته"),
    ("dormant", "غیرفعال", "بدون خرید در ۹۰ روز گذشته"),
]

DEFAULT_SMS_TEMPLATES = [
    ("order_created", "ثبت سفارش", "order", "کرامبز: سفارش {{ order_number }} ثبت شد. مبلغ {{ total }} تومان. ممنون {{ name }}!"),
    ("payment_success", "پرداخت موفق", "payment", "کرامبز: پرداخت سفارش {{ order_number }} با موفقیت انجام شد. مبلغ {{ total }} تومان."),
    ("payment_failed", "پرداخت ناموفق", "payment", "کرامبز: پرداخت سفارش {{ order_number }} ناموفق بود. لطفاً دوباره تلاش کنید."),
    ("order_confirmed_by_shop", "تأیید فروشگاه", "order", "کرامبز: سفارش {{ order_number }} توسط فروشگاه تأیید شد."),
    ("order_preparing", "در حال آماده‌سازی", "order", "کرامبز: سفارش {{ order_number }} در حال آماده‌سازی است."),
    ("order_packaged", "بسته‌بندی", "order", "کرامبز: سفارش {{ order_number }} بسته‌بندی شد."),
    ("order_out_for_delivery", "ارسال", "order", "کرامبز: سفارش {{ order_number }} در مسیر تحویل است."),
    ("delivered", "تحویل", "order", "کرامبز: سفارش {{ order_number }} تحویل داده شد. نوش جان!"),
    ("order_cancelled", "لغو سفارش", "order", "کرامبز: سفارش {{ order_number }} لغو شد."),
    ("refund_processed", "استرداد", "order", "کرامبز: استرداد سفارش {{ order_number }} انجام شد. مبلغ {{ total }} تومان."),
    ("abandoned_cart", "سبد رها شده — یادآوری ۱", "abandoned_cart", "کرامبز: {{ name }} عزیز، {{ item_count }} محصول ({{ subtotal }} تومان) در سبد شماست. {{ shop_url }}"),
    ("abandoned_cart_step2", "سبد رها شده — یادآوری ۲", "abandoned_cart", "کرامبز: {{ name }} عزیز، هنوز {{ item_count }} محصول در سبدتان است. تکمیل خرید: {{ shop_url }}"),
    ("abandoned_cart_discount", "سبد رها شده — تخفیف", "abandoned_cart", "کرامبز: {{ name }} عزیز، کد {{ coupon_code }} برای {{ discount }}% تخفیف روی سبد {{ subtotal }} تومانی. {{ shop_url }}"),
    ("cod_reminder", "یادآوری COD", "payment", "کرامبز: سفارش {{ order_number }} در راه است. مبلغ {{ total }} تومان نقدی آماده داشته باشید."),
    ("promotion", "پیشنهاد ویژه", "marketing", "{{ message }}"),
]

DEFAULT_COUPONS = [
    {
        "code": "WELCOME10",
        "name": "Welcome 10% off",
        "discount_type": Coupon.DiscountType.PERCENTAGE,
        "discount_value": "10",
        "campaign_type": Coupon.CampaignType.FIRST_ORDER,
        "usage_limit_per_user": 1,
    },
    {
        "code": "CARTSAVE15",
        "name": "Abandoned cart recovery",
        "discount_type": Coupon.DiscountType.PERCENTAGE,
        "discount_value": "15",
        "campaign_type": Coupon.CampaignType.ABANDONED_CART,
        "usage_limit_per_user": 1,
        "usage_limit_global": 500,
    },
]

DEFAULT_PROMOTION_RULES = [
    {
        "name": "Weekend cookie discount",
        "rule_type": PromotionRule.RuleType.WEEKEND_DISCOUNT,
        "config": {"percent": 10, "weekdays": [3, 4]},
        "priority": 10,
    },
    {
        "name": "VIP extra 10%",
        "rule_type": PromotionRule.RuleType.VIP_DISCOUNT,
        "config": {"percent": 10, "tiers": ["gold"]},
        "priority": 20,
    },
]


class Command(BaseCommand):
    help = "Seed default SMS templates, segments, coupons, and promotion rules."

    def handle(self, *args, **options):
        for code, name, description in DEFAULT_SEGMENTS:
            CustomerSegment.objects.update_or_create(
                code=code,
                defaults={"name": name, "description": description, "is_active": True},
            )

        for code, name, category, body in DEFAULT_SMS_TEMPLATES:
            SMSTemplate.objects.update_or_create(
                code=code,
                defaults={"name": name, "category": category, "body": body, "is_active": True},
            )

        for coupon_data in DEFAULT_COUPONS:
            code = coupon_data.pop("code")
            Coupon.objects.update_or_create(code=code, defaults={**coupon_data, "is_active": True})

        for rule_data in DEFAULT_PROMOTION_RULES:
            name = rule_data.pop("name")
            PromotionRule.objects.update_or_create(name=name, defaults={**rule_data, "is_active": True})

        self.stdout.write(self.style.SUCCESS("Growth defaults seeded successfully."))
