from django.core.management.base import BaseCommand

from growth.tasks import refresh_customer_segments_task


class Command(BaseCommand):
    help = "Refresh CRM customer segment assignments (via Celery task)."

    def handle(self, *args, **options):
        payload = refresh_customer_segments_task.apply().get()
        updated = payload.get("updated", 0)
        self.stdout.write(self.style.SUCCESS(f"Assigned {updated} new segment membership(s)."))
