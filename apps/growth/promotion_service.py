"""Rule-based promotion evaluation — admin-configurable, no code deploys."""

from dataclasses import dataclass, field
from decimal import Decimal

from django.utils import timezone

from growth.models import PromotionRule
from loyalty.models import LoyaltyAccount


@dataclass
class PromotionResult:
    total_discount: Decimal = Decimal("0.00")
    applied_rules: list[dict] = field(default_factory=list)


class PromotionRuleService:
    @classmethod
    def evaluate(cls, cart, *, user=None, subtotal: Decimal) -> PromotionResult:
        result = PromotionResult()
        rules = PromotionRule.objects.filter(is_active=True).order_by("priority", "id")

        for rule in rules:
            if not rule.is_valid_now:
                continue

            discount, label = cls._apply_rule(rule, cart, user=user, subtotal=subtotal)
            if discount <= 0:
                continue

            result.total_discount += discount
            result.applied_rules.append(
                {"rule_id": rule.pk, "name": rule.name, "discount": str(discount), "label": label}
            )

            if rule.rule_type != PromotionRule.RuleType.VIP_DISCOUNT:
                break

        result.total_discount = min(result.total_discount, subtotal)
        return result

    @classmethod
    def _apply_rule(cls, rule: PromotionRule, cart, *, user, subtotal: Decimal) -> tuple[Decimal, str]:
        config = rule.config or {}
        rule_type = rule.rule_type

        if rule_type == PromotionRule.RuleType.WEEKEND_DISCOUNT:
            now = timezone.localtime()
            allowed_days = config.get("weekdays", [4, 5])
            if now.weekday() not in allowed_days:
                return Decimal("0.00"), ""
            percent = Decimal(str(config.get("percent", 10)))
            return (subtotal * percent / Decimal("100")).quantize(Decimal("0.01")), rule.name

        if rule_type == PromotionRule.RuleType.VIP_DISCOUNT:
            if not user:
                return Decimal("0.00"), ""
            account = LoyaltyAccount.objects.filter(user=user).first()
            tiers = config.get("tiers", [LoyaltyAccount.Tier.GOLD])
            if not account or account.tier not in tiers:
                clv = getattr(user, "clv_profile", None)
                if not clv or clv.revenue_tier != "high":
                    return Decimal("0.00"), ""
            percent = Decimal(str(config.get("percent", 10)))
            return (subtotal * percent / Decimal("100")).quantize(Decimal("0.01")), rule.name

        if rule_type == PromotionRule.RuleType.CATEGORY_DISCOUNT:
            category_slugs = config.get("category_slugs", [])
            percent = Decimal(str(config.get("percent", 10)))
            eligible = Decimal("0.00")
            for item in cart.items.select_related("product__category"):
                if item.product.category.slug in category_slugs:
                    eligible += item.line_total
            if eligible <= 0:
                return Decimal("0.00"), ""
            return (eligible * percent / Decimal("100")).quantize(Decimal("0.01")), rule.name

        if rule_type == PromotionRule.RuleType.BUY_X_GET_Y:
            buy_qty = int(config.get("buy_qty", 2))
            category_slugs = config.get("buy_category_slugs", [])
            free_value = Decimal(str(config.get("free_item_value", 0)))
            if free_value <= 0:
                return Decimal("0.00"), ""

            qualifying_qty = 0
            for item in cart.items.select_related("product__category"):
                if not category_slugs or item.product.category.slug in category_slugs:
                    qualifying_qty += item.quantity

            sets = qualifying_qty // buy_qty
            if sets <= 0:
                return Decimal("0.00"), ""
            return (free_value * sets).quantize(Decimal("0.01")), rule.name

        return Decimal("0.00"), ""
