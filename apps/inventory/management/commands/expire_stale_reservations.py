from django.core.management.base import BaseCommand

from inventory.tasks import expire_stale_reservations_task


class Command(BaseCommand):
    help = "Expire stale cart/checkout stock reservations (via Celery task)."

    def handle(self, *args, **options):
        payload = expire_stale_reservations_task.apply().get()
        count = payload.get("expired", 0)
        self.stdout.write(self.style.SUCCESS(f"Expired {count} reservation(s)."))
