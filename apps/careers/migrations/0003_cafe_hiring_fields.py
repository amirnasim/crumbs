import datetime

import careers.models
import django.core.validators
from django.db import migrations, models


POSITION_ALIASES = {
    "barista": "barista",
    "cashier": "cashier",
    "waiter": "waiter",
    "waiter / waitress": "waiter",
    "assistant cook": "assistant_cook",
    "cook": "cook",
    "chef": "cook",
    "shift manager": "shift_manager",
    "cleaning staff": "cleaning_staff",
    "other": "other",
}


def forwards_copy_legacy_fields(apps, schema_editor):
    CareerApplication = apps.get_model("careers", "CareerApplication")
    for application in CareerApplication.objects.all():
        updates = {}

        cover_letter = getattr(application, "cover_letter", "") or ""
        hr_answers = dict(application.hr_answers or {})
        if cover_letter and not hr_answers:
            hr_answers["why_crumbs"] = cover_letter
            updates["hr_answers"] = hr_answers

        raw_position = (application.desired_position or "").strip()
        normalized = POSITION_ALIASES.get(raw_position.lower(), "other")
        if raw_position and normalized != raw_position:
            updates["desired_position"] = normalized

        if updates:
            for field, value in updates.items():
                setattr(application, field, value)
            application.save(update_fields=list(updates.keys()))


class Migration(migrations.Migration):

    dependencies = [
        ("careers", "0002_remove_social_urls"),
    ]

    operations = [
        migrations.AddField(
            model_name="careerapplication",
            name="available_from",
            field=models.DateField(default=datetime.date(2026, 1, 1)),
            preserve_default=False,
        ),
        migrations.AddField(
            model_name="careerapplication",
            name="hr_answers",
            field=models.JSONField(blank=True, default=dict),
        ),
        migrations.RunPython(forwards_copy_legacy_fields, migrations.RunPython.noop),
        migrations.RemoveField(
            model_name="careerapplication",
            name="cover_letter",
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="desired_position",
            field=models.CharField(
                choices=[
                    ("barista", "Barista"),
                    ("cashier", "Cashier"),
                    ("waiter", "Waiter / Waitress"),
                    ("assistant_cook", "Assistant Cook"),
                    ("cook", "Cook"),
                    ("shift_manager", "Shift Manager"),
                    ("cleaning_staff", "Cleaning Staff"),
                    ("other", "Other"),
                ],
                db_index=True,
                max_length=32,
            ),
        ),
        migrations.AlterField(
            model_name="careerapplication",
            name="resume_file",
            field=models.FileField(
                blank=True,
                upload_to=careers.models.career_resume_upload_path,
                validators=[
                    django.core.validators.FileExtensionValidator(
                        allowed_extensions=["pdf"]
                    )
                ],
            ),
        ),
    ]
