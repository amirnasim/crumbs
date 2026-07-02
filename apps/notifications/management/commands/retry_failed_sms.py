from django.core.management.base import BaseCommand

from notifications.tasks import retry_failed_sms_task


class Command(BaseCommand):
    help = "Retry failed SMS deliveries (via Celery task)."

    def handle(self, *args, **options):
        payload = retry_failed_sms_task.apply().get()
        count = payload.get("retried", 0)
        self.stdout.write(self.style.SUCCESS(f"Retried {count} failed SMS message(s)."))
