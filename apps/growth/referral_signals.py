from django.contrib.auth import get_user_model
from django.db.models.signals import post_save
from django.dispatch import receiver

from growth.referral_service import ReferralService

User = get_user_model()


@receiver(post_save, sender=User)
def ensure_referral_code(sender, instance, created, **kwargs):
    if created:
        ReferralService.get_or_create_code(instance)
