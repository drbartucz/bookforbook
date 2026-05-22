from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0003_ensure_backup_schedules"),
    ]

    operations = [
        migrations.AddField(
            model_name="backuprecord",
            name="storage_backend",
            field=models.CharField(blank=True, max_length=200),
        ),
    ]
