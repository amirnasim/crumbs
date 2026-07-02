from decimal import Decimal

from django.core.management.base import BaseCommand

from delivery.models import DeliveryZone
from inventory.models import ProductInventory
from products.models import Product


DEFAULT_ZONES = [
    {
        "code": "tehran",
        "name": "تهران",
        "cities": ["تهران", "Tehran", "tehran"],
        "states": ["تهران", "Tehran"],
        "delivery_fee": Decimal("45000"),
        "express_fee": Decimal("85000"),
        "min_order_amount": Decimal("150000"),
        "free_delivery_threshold": Decimal("500000"),
        "sort_order": 1,
    },
    {
        "code": "tehran_suburbs",
        "name": "حومه تهران",
        "cities": ["کرج", "Karaj", "karaj", "فردیس", "پردیس", "اسلامشهر", "شهریار"],
        "states": ["البرز", "Alborz", "تهران"],
        "delivery_fee": Decimal("65000"),
        "express_fee": Decimal("95000"),
        "min_order_amount": Decimal("200000"),
        "free_delivery_threshold": Decimal("600000"),
        "sort_order": 2,
    },
    {
        "code": "other_cities",
        "name": "سایر شهرها",
        "cities": ["اصفهان", "Isfahan", "شیراز", "Shiraz", "مشهد", "Mashhad", "تبریز", "Tabriz"],
        "states": [],
        "delivery_fee": Decimal("95000"),
        "express_fee": Decimal("145000"),
        "min_order_amount": Decimal("250000"),
        "free_delivery_threshold": None,
        "sort_order": 99,
    },
]


class Command(BaseCommand):
    help = "Seed Iran delivery zones and product inventory defaults."

    def handle(self, *args, **options):
        for zone_data in DEFAULT_ZONES:
            DeliveryZone.objects.update_or_create(
                code=zone_data["code"],
                defaults={
                    "name": zone_data["name"],
                    "cities": zone_data["cities"],
                    "states": zone_data["states"],
                    "delivery_fee": zone_data["delivery_fee"],
                    "express_fee": zone_data["express_fee"],
                    "min_order_amount": zone_data["min_order_amount"],
                    "free_delivery_threshold": zone_data["free_delivery_threshold"],
                    "sort_order": zone_data["sort_order"],
                    "is_active": True,
                },
            )

        for product in Product.objects.all():
            ProductInventory.objects.get_or_create(
                product=product,
                defaults={
                    "track_stock": True,
                    "stock_quantity": 100,
                    "low_stock_threshold": 10,
                    "allow_preorder": True,
                },
            )

        self.stdout.write(self.style.SUCCESS("Iran delivery defaults seeded successfully."))
