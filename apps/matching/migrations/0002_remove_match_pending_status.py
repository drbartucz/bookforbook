from django.db import migrations, models


def migrate_pending_to_proposed(apps, schema_editor):
    Match = apps.get_model("matching", "Match")
    Match.objects.filter(status="pending").update(status="proposed")


class Migration(migrations.Migration):

    dependencies = [
        ("matching", "0001_initial"),
    ]

    operations = [
        migrations.RunPython(
            migrate_pending_to_proposed,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.AlterField(
            model_name="match",
            name="status",
            field=models.CharField(
                choices=[
                    ("proposed", "Proposed"),
                    ("expired", "Expired"),
                    ("completed", "Completed"),
                ],
                default="proposed",
                max_length=20,
            ),
        ),
    ]
