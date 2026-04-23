"""
Data migration: create Django-Q2 periodic schedules for background tasks.
"""

from django.db import migrations


def create_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")

    schedules = [
        {
            "name": "Run periodic matching",
            "func": "apps.matching.tasks.run_periodic_matching",
            "schedule_type": "I",
            "minutes": 360,
        },
        {
            "name": "Expire old matches",
            "func": "apps.matching.tasks.expire_old_matches",
            "schedule_type": "I",
            "minutes": 60,
        },
        {
            "name": "Check user inactivity",
            "func": "apps.notifications.tasks.check_inactivity",
            "schedule_type": "D",
        },
        {
            "name": "Send rating reminders",
            "func": "apps.trading.tasks.send_rating_reminders",
            "schedule_type": "W",
        },
        {
            "name": "Auto-close trades",
            "func": "apps.trading.tasks.auto_close_trades",
            "schedule_type": "W",
        },
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

    for sched in schedules:
        Schedule.objects.get_or_create(name=sched["name"], defaults=sched)


def remove_schedules(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(
        name__in=[
            "Run periodic matching",
            "Expire old matches",
            "Check user inactivity",
            "Send rating reminders",
            "Auto-close trades",
            "Nightly database backup",
            "Apply backup retention policy",
        ]
    ).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("notifications", "0001_initial"),
        ("django_q", "0001_initial"),
    ]
    operations = [
        migrations.RunPython(create_schedules, remove_schedules),
    ]
