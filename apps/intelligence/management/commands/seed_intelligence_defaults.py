from django.core.management.base import BaseCommand

from intelligence.aggregation_service import AggregationService
from notifications.models import SMSTemplate


SMS_TEMPLATES = [
    (
        "intel_cookie_offer",
        "پیشنهاد کوکی شخصی",
        "marketing",
        "کرامبز: {{ name }} عزیز، {{ product_name }} جدید را امتحان کنید! {{ shop_url }}",
    ),
    (
        "intel_vip_offer",
        "پیشنهاد VIP",
        "marketing",
        "کرامبز: {{ name }} عزیز، به عنوان مشتری VIP — {{ product_name }} مخصوص شماست. {{ shop_url }}",
    ),
]


class Command(BaseCommand):
    help = "Seed intelligence SMS templates and sync product meta."

    def handle(self, *args, **options):
        for code, name, category, body in SMS_TEMPLATES:
            SMSTemplate.objects.update_or_create(
                code=code,
                defaults={"name": name, "category": category, "body": body, "is_active": True},
            )

        meta_count = AggregationService.sync_product_intelligence_meta()
        self.stdout.write(
            self.style.SUCCESS(
                f"Intelligence defaults seeded. Product meta synced for {meta_count} products."
            )
        )
