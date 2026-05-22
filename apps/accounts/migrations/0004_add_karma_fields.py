from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0003_user_deletion_lifecycle_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="gifts_given_count",
            field=models.PositiveIntegerField(default=0),
        ),
        migrations.AddField(
            model_name="user",
            name="giver_badge",
            field=models.CharField(
                blank=True,
                choices=[("top_10", "Top 10%"), ("top_25", "Top 25%")],
                max_length=10,
                null=True,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="trader_badge",
            field=models.CharField(
                blank=True,
                choices=[("top_10", "Top 10%"), ("top_25", "Top 25%")],
                max_length=10,
                null=True,
            ),
        ),
    ]
