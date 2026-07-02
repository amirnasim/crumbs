from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("orders", "0004_revenue_engine"),
    ]

    operations = [
        migrations.AlterField(
            model_name="order",
            name="payment_method",
            field=models.CharField(
                choices=[
                    ("cod", "Cash on Delivery"),
                    ("online", "Online Payment"),
                    ("cash", "Cash at Counter"),
                    ("counter_card", "Card at Counter"),
                ],
                db_index=True,
                default="online",
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending_payment", "Pending Payment"),
                    ("awaiting_payment", "Awaiting Payment"),
                    ("paid", "Paid"),
                    ("confirmed_by_shop", "Confirmed by Shop"),
                    ("preparing", "Preparing"),
                    ("packaged", "Packaged"),
                    ("out_for_delivery", "Out for Delivery"),
                    ("delivered", "Delivered"),
                    ("cancelled", "Cancelled"),
                    ("refunded", "Refunded"),
                ],
                db_index=True,
                default="pending_payment",
                max_length=30,
            ),
        ),
    ]
