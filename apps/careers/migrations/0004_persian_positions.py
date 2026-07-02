from django.db import migrations, models


LEGACY_POSITION_MAP = {
    "assistant_cook": "kitchen_staff",
    "cook": "kitchen_staff",
    "shift_manager": "shift_supervisor",
    "cleaning_staff": "cleaner",
    "other": "kitchen_staff",
}


def forwards_migrate_positions(apps, schema_editor):
    CareerApplication = apps.get_model("careers", "CareerApplication")
    for application in CareerApplication.objects.all():
        new_value = LEGACY_POSITION_MAP.get(application.desired_position)
        if new_value:
            application.desired_position = new_value
            application.save(update_fields=["desired_position"])


class Migration(migrations.Migration):

    dependencies = [
        ("careers", "0003_cafe_hiring_fields"),
    ]

    operations = [
        migrations.RunPython(forwards_migrate_positions, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="careerapplication",
            name="desired_position",
            field=models.CharField(
                choices=[
                    ("barista", "باریستا"),
                    ("cashier", "صندوق‌دار"),
                    ("waiter", "گارسون"),
                    ("kitchen_staff", "نیروی آشپزخانه"),
                    ("baker", "نانوا"),
                    ("pastry_assistant", "کمک قناد"),
                    ("shift_supervisor", "سرپرست شیفت"),
                    ("cleaner", "خدمات و نظافت"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="موقعیت شغلی",
            ),
        ),
    ]
