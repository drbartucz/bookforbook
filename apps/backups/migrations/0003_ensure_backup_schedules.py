"""Ensure backup schedules exist."""

from django.db import migrations


def ensure_schedules(apps, schema_editor):
    try:
        Schedule = apps.get_model("django_q", "Schedule")
    except LookupError:
        # django-q might not be installed or migrations not run yet
        return

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
        obj, created = Schedule.objects.get_or_create(
            name=schedule["name"],
            defaults=schedule
        )
        if not created:
            # Update existing if needed, but primarily ensure they exist
            for key, value in schedule.items():
                setattr(obj, key, value)
            obj.save()


class Migration(migrations.Migration):
    dependencies = [
        ("backups", "0002_create_q_schedules"),
        ("django_q", "0008_auto_20160224_1026"),
    ]

    operations = [
        migrations.RunPython(ensure_schedules, migrations.RunPython.noop),
    ]
