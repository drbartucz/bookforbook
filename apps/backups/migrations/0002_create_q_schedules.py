"""Create Django-Q schedules for backups tasks."""

from django.db import migrations


def create_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")

    schedules = [
        {
            "name": "Nightly database backup",
            "func": "apps.backups.tasks.nightly_database_backup",
            "schedule_type": "D",
            "repeats": -1,
        },
        {
            "name": "Apply backup retention policy",
            "func": "apps.backups.tasks.apply_backup_retention_policy",
            "schedule_type": "W",
            "repeats": -1,
        },
    ]

    for schedule in schedules:
        Schedule.objects.get_or_create(name=schedule["name"], defaults=schedule)


def remove_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(
        name__in=[
            "Nightly database backup",
            "Apply backup retention policy",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0001_initial"),
        ("django_q", "0008_auto_20160224_1026"),
    ]

    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
