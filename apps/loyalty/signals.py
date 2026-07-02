from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from .services import get_or_create_account

User = get_user_model()


@receiver(post_save, sender=User)
def create_loyalty_account(sender, instance, created, **kwargs):
    if created:
        get_or_create_account(instance)
