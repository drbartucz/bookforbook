import uuid

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackupRecord",
            fields=[
                (
                    "id",
                    models.UUIDField(
                        default=uuid.uuid4,
                        editable=False,
                        primary_key=True,
                        serialize=False,
                    ),
                ),
                (
                    "backup_type",
                    models.CharField(
                        choices=[("database", "Database")],
                        default="database",
                        max_length=20,
                    ),
                ),
                (
                    "status",
                    models.CharField(
                        choices=[
                            ("pending", "Pending"),
                            ("running", "Running"),
                            ("success", "Success"),
                            ("failed", "Failed"),
                        ],
                        default="pending",
                        max_length=20,
                    ),
                ),
                ("file_name", models.CharField(blank=True, max_length=500)),
                ("file_size_bytes", models.BigIntegerField(blank=True, null=True)),
                ("error_message", models.TextField(blank=True)),
                ("is_automatic", models.BooleanField(default=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("completed_at", models.DateTimeField(blank=True, null=True)),
                (
                    "triggered_by",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="triggered_backups",
                        to="accounts.user",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backup Record",
                "verbose_name_plural": "Backup Records",
                "ordering": ["-created_at"],
            },
        ),
    ]
