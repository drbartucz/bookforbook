from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("inventory", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="wishlistitem",
            name="allow_translations",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="wishlistitem",
            name="edition_preference",
            field=models.CharField(
                choices=[
                    ("exact", "Exact edition only"),
                    ("same_language", "Same work, same language"),
                    ("any_language", "Same work, any language"),
                    ("custom", "Custom rules"),
                ],
                default="same_language",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="wishlistitem",
            name="exclude_abridged",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="wishlistitem",
            name="format_preferences",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
