from django.core.management.base import BaseCommand

from growth.tasks import send_abandoned_cart_sms


class Command(BaseCommand):
    help = "Send SMS reminders for abandoned carts (via Celery task)."

    def handle(self, *args, **options):
        payload = send_abandoned_cart_sms.apply().get()
        sent = payload.get("sent", 0)
        self.stdout.write(self.style.SUCCESS(f"Queued/sent {sent} abandoned cart SMS reminder(s)."))
