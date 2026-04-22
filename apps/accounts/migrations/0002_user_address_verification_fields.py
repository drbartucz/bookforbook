from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="address_verification_status",
            field=models.CharField(
                choices=[
                    ("unverified", "Unverified"),
                    ("verified", "Verified"),
                    ("failed", "Failed"),
                ],
                default="unverified",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="address_verified_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
    ]
