from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_user_address_verification_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="deletion_completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="deletion_requested_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="user",
            name="deletion_scheduled_for",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
