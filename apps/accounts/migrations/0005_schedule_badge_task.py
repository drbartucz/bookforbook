"""Schedule the nightly karma badge recalculation task in Django-Q."""

from django.db import migrations


def create_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.get_or_create(
        name="Recalculate karma badges",
        defaults={
            "func": "apps.accounts.tasks.recalculate_karma_badges",
            "schedule_type": "D",
            "repeats": -1,
        },
    )


def remove_schedule(apps, schema_editor):
    Schedule = apps.get_model("django_q", "Schedule")
    Schedule.objects.filter(name="Recalculate karma badges").delete()


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_add_karma_fields"),
        ("django_q", "0008_auto_20160224_1026"),
    ]

    operations = [
        migrations.RunPython(create_schedule, remove_schedule),
    ]
