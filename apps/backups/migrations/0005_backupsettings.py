from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0004_backuprecord_storage_backend"),
    ]

    operations = [
        migrations.CreateModel(
            name="BackupSettings",
            fields=[
                ("id", models.AutoField(primary_key=True, serialize=False)),
                (
                    "email_on_success",
                    models.BooleanField(
                        default=False,
                        help_text="Send an email to the admin alert address whenever a backup succeeds.",
                    ),
                ),
                (
                    "email_on_failure",
                    models.BooleanField(
                        default=True,
                        help_text="Send an email to the admin alert address whenever a backup fails.",
                    ),
                ),
            ],
            options={
                "verbose_name": "Backup Settings",
                "verbose_name_plural": "Backup Settings",
            },
        ),
    ]
