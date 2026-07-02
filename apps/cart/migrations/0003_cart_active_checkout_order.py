from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("orders", "0001_initial"),
        ("cart", "0002_revenue_engine"),
    ]

    operations = [
        migrations.AddField(
            model_name="cart",
            name="active_checkout_order",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name="checkout_source_cart",
                to="orders.order",
            ),
        ),
    ]
