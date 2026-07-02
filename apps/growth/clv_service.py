"""Customer lifetime value calculation and revenue tier segmentation."""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.db.models import Avg, Count, Max, Sum
from django.utils import timezone

from growth.models import CustomerCLVProfile
from orders.models import Order

User = get_user_model()

PAID_STATUSES = (Order.PaymentStatus.PAID, Order.PaymentStatus.CASH_RECEIVED)


class CLVService:
    LOW_THRESHOLD = Decimal("500000")
    HIGH_THRESHOLD = Decimal("5000000")

    @classmethod
    def calculate_for_user(cls, user) -> CustomerCLVProfile:
        stats = Order.objects.filter(user=user, payment_status__in=PAID_STATUSES).aggregate(
            revenue=Sum("total"),
            count=Count("id"),
            avg=Avg("total"),
            last=Max("created_at"),
        )
        revenue = stats["revenue"] or Decimal("0.00")
        order_count = stats["count"] or 0
        avg_order = stats["avg"] or Decimal("0.00")
        last_order = stats["last"]

        clv_score = revenue + (avg_order * Decimal(str(min(order_count, 12))))

        if revenue >= cls.HIGH_THRESHOLD:
            tier = CustomerCLVProfile.RevenueTier.HIGH
        elif revenue >= cls.LOW_THRESHOLD:
            tier = CustomerCLVProfile.RevenueTier.MEDIUM
        else:
            tier = CustomerCLVProfile.RevenueTier.LOW

        frequency = cls._frequency_tag(order_count, last_order)

        profile, _ = CustomerCLVProfile.objects.update_or_create(
            user=user,
            defaults={
                "lifetime_revenue": revenue,
                "order_count": order_count,
                "avg_order_value": avg_order,
                "clv_score": clv_score,
                "revenue_tier": tier,
                "frequency_tag": frequency,
                "last_order_at": last_order,
            },
        )
        return profile

    @staticmethod
    def _frequency_tag(order_count: int, last_order_at) -> str:
        if order_count == 0:
            return CustomerCLVProfile.FrequencyTag.NEW
        if order_count >= 10:
            return CustomerCLVProfile.FrequencyTag.LOYAL
        if order_count >= 4:
            return CustomerCLVProfile.FrequencyTag.REGULAR
        return CustomerCLVProfile.FrequencyTag.OCCASIONAL

    @classmethod
    def refresh_all(cls) -> int:
        updated = 0
        for user in User.objects.filter(is_active=True):
            cls.calculate_for_user(user)
            updated += 1
        return updated

    @classmethod
    def get_vip_customers(cls, limit: int = 20):
        return (
            CustomerCLVProfile.objects.filter(revenue_tier=CustomerCLVProfile.RevenueTier.HIGH)
            .select_related("user")
            .order_by("-clv_score")[:limit]
        )
