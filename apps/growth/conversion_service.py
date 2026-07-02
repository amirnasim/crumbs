"""Lightweight conversion funnel event tracking."""

from django.contrib.auth import get_user_model

from growth.models import GrowthEvent

User = get_user_model()


class ConversionService:
    @staticmethod
    def track(
        event_type: str,
        *,
        user=None,
        session_key: str = "",
        product=None,
        cart=None,
        order=None,
        metadata: dict | None = None,
    ) -> GrowthEvent:
        return GrowthEvent.objects.create(
            event_type=event_type,
            user=user,
            session_key=session_key or "",
            product=product,
            cart=cart,
            order=order,
            metadata=metadata or {},
        )

    @classmethod
    def aggregate_funnel(cls, since, until=None) -> dict:
        qs = GrowthEvent.objects.filter(created_at__gte=since)
        if until:
            qs = qs.filter(created_at__lt=until)

        def count(event_type):
            return qs.filter(event_type=event_type).count()

        product_views = count(GrowthEvent.EventType.PRODUCT_VIEW)
        add_to_cart = count(GrowthEvent.EventType.ADD_TO_CART)
        checkout_starts = count(GrowthEvent.EventType.CHECKOUT_START)
        checkout_complete = count(GrowthEvent.EventType.CHECKOUT_COMPLETE)
        sms_sent = count(GrowthEvent.EventType.SMS_SENT)
        sms_conversions = count(GrowthEvent.EventType.SMS_CONVERSION)

        view_to_cart = (add_to_cart / product_views * 100) if product_views else 0
        cart_to_checkout = (checkout_starts / add_to_cart * 100) if add_to_cart else 0
        checkout_conversion = (checkout_complete / checkout_starts * 100) if checkout_starts else 0
        sms_conversion_rate = (sms_conversions / sms_sent * 100) if sms_sent else 0

        return {
            "product_views": product_views,
            "add_to_cart": add_to_cart,
            "checkout_starts": checkout_starts,
            "checkout_complete": checkout_complete,
            "sms_sent": sms_sent,
            "sms_conversions": sms_conversions,
            "view_to_cart_rate": round(view_to_cart, 2),
            "cart_to_checkout_rate": round(cart_to_checkout, 2),
            "checkout_conversion_rate": round(checkout_conversion, 2),
            "sms_conversion_rate": round(sms_conversion_rate, 2),
            "cart_abandonment_rate": round(100 - checkout_conversion, 2) if checkout_starts else 0,
        }
