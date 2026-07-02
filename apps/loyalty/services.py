from decimal import Decimal

from django.conf import settings
from django.db import transaction

from loyalty.models import LoyaltyAccount, LoyaltyTransaction
from orders.models import Order


def get_or_create_account(user) -> LoyaltyAccount:
    account, _ = LoyaltyAccount.objects.get_or_create(user=user)
    return account


def calculate_tier(lifetime_points: int) -> str:
    gold = settings.LOYALTY_GOLD_THRESHOLD
    silver = settings.LOYALTY_SILVER_THRESHOLD
    if lifetime_points >= gold:
        return LoyaltyAccount.Tier.GOLD
    if lifetime_points >= silver:
        return LoyaltyAccount.Tier.SILVER
    return LoyaltyAccount.Tier.NORMAL


def points_for_order_total(total: Decimal) -> int:
    rate = settings.LOYALTY_POINTS_PER_1000_TOMAN
    return int(total // 1000) * rate


@transaction.atomic
def award_points_for_order(order) -> LoyaltyAccount | None:
    paid_statuses = {order.PaymentStatus.PAID, order.PaymentStatus.CASH_RECEIVED}
    if not order.user_id or order.payment_status not in paid_statuses:
        return None

    if LoyaltyTransaction.objects.filter(
        order=order,
        transaction_type=LoyaltyTransaction.Type.EARN,
    ).exists():
        return None

    account = get_or_create_account(order.user)
    earned = points_for_order_total(order.total)
    if earned <= 0:
        return account

    account.points += earned
    account.lifetime_points += earned
    account.lifetime_spend += order.total
    account.tier = calculate_tier(account.lifetime_points)
    account.save(update_fields=["points", "lifetime_points", "lifetime_spend", "tier", "updated_at"])

    LoyaltyTransaction.objects.create(
        account=account,
        transaction_type=LoyaltyTransaction.Type.EARN,
        points=earned,
        balance_after=account.points,
        order=order,
        description=f"Points for order {order.order_number}",
    )
    return account
