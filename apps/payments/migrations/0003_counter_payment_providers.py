from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("payments", "0002_alter_payment_currency_alter_payment_provider_and_more"),
    ]

    operations = [
        migrations.AlterField(
            model_name="payment",
            name="provider",
            field=models.CharField(
                choices=[
                    ("zarinpal", "Zarinpal"),
                    ("stripe", "Stripe"),
                    ("cod", "Cash on Delivery"),
                    ("cash", "Counter Cash"),
                    ("counter_card", "Counter Card"),
                ],
                db_index=True,
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="paymentevent",
            name="provider",
            field=models.CharField(
                choices=[
                    ("zarinpal", "Zarinpal"),
                    ("stripe", "Stripe"),
                    ("cod", "Cash on Delivery"),
                    ("cash", "Counter Cash"),
                    ("counter_card", "Counter Card"),
                ],
                max_length=20,
            ),
        ),
    ]
