from django.db import migrations, models


def populate_missing_emails(apps, schema_editor):
    CareerApplication = apps.get_model("careers", "CareerApplication")
    for application in CareerApplication.objects.filter(email=""):
        application.email = f"applicant-{application.pk}@crumbs.local"
        application.save(update_fields=["email"])


class Migration(migrations.Migration):

    dependencies = [
        ("careers", "0006_align_model_verbose_names"),
    ]

    operations = [
        migrations.RunPython(populate_missing_emails, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="careerapplication",
            name="desired_position",
            field=models.CharField(
                choices=[
                    ("barista", "باریستا"),
                    ("cashier", "صندوق\u200cدار / فروشنده"),
                    ("cold_bar", "بار سرد"),
                    ("waiter", "سالن کار"),
                    ("kitchen_staff", "نیروی آشپزخانه"),
                    ("baker", "بیکر"),
                    ("pastry_assistant", "کمک بیکر"),
                    ("shift_supervisor", "سرپرست شیفت"),
                    ("cleaner", "خدمات و نظافت"),
                ],
                db_index=True,
                max_length=32,
                verbose_name="موقعیت شغلی",
            ),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="email",
            field=models.EmailField(max_length=254, verbose_name="ایمیل"),
        ),
    ]
