from django.db.models.signals import post_delete, post_save, pre_save
from django.dispatch import receiver

from cart.models import Cart, CartItem
from growth.services import sync_abandoned_cart_tracker
from orders.events import emit_order_lifecycle_events
from orders.models import Order


@receiver(pre_save, sender=Order)
def cache_order_previous_state(sender, instance, **kwargs):
    if not instance.pk:
        instance._prev_payment_status = None
        instance._prev_status = None
        return
    try:
        previous = Order.objects.get(pk=instance.pk)
        instance._prev_payment_status = previous.payment_status
        instance._prev_status = previous.status
    except Order.DoesNotExist:
        instance._prev_payment_status = None
        instance._prev_status = None


@receiver(post_save, sender=Order)
def enqueue_order_lifecycle_events(sender, instance, created, **kwargs):
    """Emit async order events — SMS, loyalty, analytics handled by Celery workers."""
    emit_order_lifecycle_events(
        instance,
        created=created,
        prev_payment=getattr(instance, "_prev_payment_status", None),
        prev_status=getattr(instance, "_prev_status", None),
    )


@receiver(post_save, sender=Cart)
def sync_tracker_on_cart_save(sender, instance, **kwargs):
    sync_abandoned_cart_tracker(instance)


@receiver(post_save, sender=CartItem)
def sync_tracker_on_item_save(sender, instance, **kwargs):
    sync_abandoned_cart_tracker(instance.cart)


@receiver(post_delete, sender=CartItem)
def sync_tracker_on_item_delete(sender, instance, **kwargs):
    sync_abandoned_cart_tracker(instance.cart)
