from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="BackgroundTaskLog",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("task_name", models.CharField(db_index=True, max_length=255)),
                ("task_id", models.CharField(max_length=255, unique=True)),
                ("idempotency_key", models.CharField(blank=True, db_index=True, max_length=255)),
                ("queue", models.CharField(blank=True, max_length=64)),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("started", "Started"),
                            ("success", "Success"),
                            ("failure", "Failure"),
                            ("retry", "Retry"),
                            ("dead", "Dead Letter"),
                        ],
                        default="pending",
                        max_length=16,
                    ),
                ),
                ("payload", models.JSONField(blank=True, default=dict)),
                ("result", models.JSONField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
        migrations.CreateModel(
            name="DailyAnalyticsSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("report_date", models.DateField(unique=True)),
                ("payload", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "ordering": ["-report_date"],
            },
        ),
        migrations.AddIndex(
            model_name="backgroundtasklog",
            index=models.Index(fields=["task_name", "status"], name="core_backgr_task_na_6f8b2a_idx"),
        ),
        migrations.AddIndex(
            model_name="backgroundtasklog",
            index=models.Index(fields=["created_at"], name="core_backgr_created_0a1c4d_idx"),
        ),
    ]
