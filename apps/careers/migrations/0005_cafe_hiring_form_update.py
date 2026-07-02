import django.core.validators
from django.db import migrations, models


def strip_shift_availability_from_hr_answers(apps, schema_editor):
    CareerApplication = apps.get_model("careers", "CareerApplication")
    for application in CareerApplication.objects.all():
        if not application.hr_answers:
            continue
        if "shift_availability" not in application.hr_answers:
            continue
        hr_answers = dict(application.hr_answers)
        hr_answers.pop("shift_availability", None)
        application.hr_answers = hr_answers
        application.save(update_fields=["hr_answers"])


class Migration(migrations.Migration):

    dependencies = [
        ("careers", "0004_persian_positions"),
    ]

    operations = [
        migrations.AddField(
            model_name="careerapplication",
            name="age",
            field=models.PositiveSmallIntegerField(
                default=18,
                validators=[
                    django.core.validators.MinValueValidator(16),
                    django.core.validators.MaxValueValidator(80),
                ],
                verbose_name="سن",
            ),
        ),
        migrations.AddField(
            model_name="careerapplication",
            name="residential_area",
            field=models.CharField(default="—", max_length=120, verbose_name="منطقه زندگی"),
        ),
        migrations.AddField(
            model_name="careerapplication",
            name="employment_type",
            field=models.CharField(
                choices=[("full_time", "تمام‌وقت"), ("part_time", "پاره‌وقت")],
                default="full_time",
                max_length=16,
                verbose_name="نوع همکاری",
            ),
        ),
        migrations.AddField(
            model_name="careerapplication",
            name="relevant_experience",
            field=models.TextField(default="—", verbose_name="سابقه کار مرتبط"),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="age",
            field=models.PositiveSmallIntegerField(
                validators=[
                    django.core.validators.MinValueValidator(16),
                    django.core.validators.MaxValueValidator(80),
                ],
                verbose_name="سن",
            ),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="residential_area",
            field=models.CharField(max_length=120, verbose_name="منطقه زندگی"),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="employment_type",
            field=models.CharField(
                choices=[("full_time", "تمام‌وقت"), ("part_time", "پاره‌وقت")],
                max_length=16,
                verbose_name="نوع همکاری",
            ),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="relevant_experience",
            field=models.TextField(verbose_name="سابقه کار مرتبط"),
        ),
        migrations.RunPython(strip_shift_availability_from_hr_answers, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="careerapplication",
            name="available_from",
        ),
    ]
